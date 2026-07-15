"""Streaming live-data report rendering service."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from time import monotonic

from ..data_sources import DatasetField
from ..dataset_execution import (
    DatasetExecutionCancellationToken,
    DatasetExecutionCancelledError,
    DatasetExecutionOptions,
    DatasetExecutionTimeoutError,
    DatasetResultLimitError,
)
from ..models import Object
from ..rendering.context import (
    RenderContext,
    RenderObject,
    context_with_page_numbers,
    convert_unit,
    create_render_context,
    object_px,
)
from ..rendering.html_renderer import render_html_band, render_html_object
from ..rendering.pagination import get_pagination_settings
from ..report import Report
from .binding import RuntimeBindingResolver, RuntimeValueFormatter
from .context import resolve_runtime_dataset, validate_runtime_bindings
from .errors import (
    RuntimeBandConfigurationError,
    RuntimePreviewCancelledError,
    RuntimePreviewTimeoutError,
    RuntimeReportLimitError,
)
from .html import render_runtime_document, runtime_page_html
from .models import (
    RuntimePreviewOptions,
    RuntimePreviewPolicy,
    RuntimePreviewResult,
    RuntimePreviewSummary,
    RuntimePreviewWarning,
)

logger = logging.getLogger(__name__)


@dataclass
class _PageBuffer:
    detail_bands: list[str]
    detail_objects: list[str]


class RuntimeReportRenderService:
    """Execute one MySQL dataset and render its Detail rows incrementally."""

    def __init__(
        self,
        *,
        execution_service: object,
        binding_resolver: RuntimeBindingResolver | None = None,
        value_formatter: RuntimeValueFormatter | None = None,
        policy: RuntimePreviewPolicy | None = None,
    ) -> None:
        self.execution_service = execution_service
        self.binding_resolver = binding_resolver or RuntimeBindingResolver()
        self.value_formatter = value_formatter or RuntimeValueFormatter()
        self.policy = policy or RuntimePreviewPolicy()
        execution_policy = getattr(execution_service, "policy", None)
        execution_max_rows = getattr(execution_policy, "max_rows", None)
        if isinstance(execution_max_rows, int) and self.policy.max_rows > execution_max_rows:
            raise ValueError("Preview row limit must not exceed the execution row limit.")

    def render_html(
        self,
        report: Report,
        *,
        dataset_id: str | None = None,
        parameter_values: Mapping[str, object] | None = None,
        options: RuntimePreviewOptions | None = None,
        cancellation_token: DatasetExecutionCancellationToken | None = None,
        asset_provider: object | None = None,
        asset_resolver: object | None = None,
    ) -> RuntimePreviewResult:
        if not isinstance(report, Report):
            raise RuntimeBandConfigurationError("Live preview requires a Report instance.")
        selected_options = options or RuntimePreviewOptions(dataset_id=dataset_id)
        if (
            dataset_id is not None
            and selected_options.dataset_id is not None
            and dataset_id != selected_options.dataset_id
        ):
            raise ValueError("Conflicting preview dataset IDs were provided.")
        explicit_dataset = dataset_id or selected_options.dataset_id
        max_rows = self._effective_limit(
            "max_rows", selected_options.max_rows, self.policy.max_rows
        )
        timeout = self._effective_limit(
            "timeout_seconds",
            selected_options.timeout_seconds,
            self.policy.max_elapsed_seconds,
        )
        token = cancellation_token or DatasetExecutionCancellationToken()
        started = monotonic()

        dataset = resolve_runtime_dataset(report, self.execution_service, explicit_dataset)
        validate_runtime_bindings(report, dataset)
        context = create_render_context(
            report,
            report.data,
            asset_provider=asset_provider,
            asset_resolver=asset_resolver,
        )
        layout = self._layout(report, context, dataset.id)
        self._check_deadline(started, timeout, token)
        logger.info(
            "Live report preview started for dataset %s: rows=%d, timeout=%d.",
            dataset.id,
            max_rows,
            timeout,
        )

        pages = [_PageBuffer([], [])]
        row_count = 0
        object_count = 0
        execution_summary = None
        try:
            stream = self.execution_service.open_dataset(
                report,
                dataset.id,
                parameter_values=parameter_values,
                options=DatasetExecutionOptions(max_rows=max_rows, timeout_seconds=timeout),
                cancellation_token=token,
            )
            with stream:
                for row in stream:
                    self._check_deadline(started, timeout, token)
                    page_index = row_count // layout.rows_per_page
                    if page_index >= self.policy.max_pages:
                        raise RuntimeReportLimitError(
                            f"Report preview exceeded the configured page limit of "
                            f"{self.policy.max_pages} pages."
                        )
                    if page_index == len(pages):
                        pages.append(_PageBuffer([], []))
                    local_index = row_count % layout.rows_per_page
                    row_y = layout.content_top_px + (local_index * layout.row_height_px)
                    page = pages[page_index]
                    page.detail_bands.append(
                        self._detail_band_html(
                            layout.detail_render_band,
                            row_y,
                            layout.row_height_px,
                            row_count,
                        )
                    )
                    row_context = self._row_context(context, row.values)
                    for domain_object, render_object in layout.detail_objects:
                        object_count = self._claim_object(object_count)
                        rendered = self._render_detail_object(
                            domain_object,
                            render_object,
                            row,
                            dataset,
                            row_context,
                            row_y,
                            layout.detail_origin_px,
                            row_count,
                        )
                        page.detail_objects.append(rendered)
                    row_count += 1
                execution_summary = stream.summary()
        except DatasetExecutionCancelledError as exc:
            raise RuntimePreviewCancelledError("Report preview was cancelled.") from exc
        except DatasetExecutionTimeoutError as exc:
            raise RuntimePreviewTimeoutError("Report preview timed out.") from exc
        except DatasetResultLimitError as exc:
            raise RuntimeReportLimitError(
                "Report preview exceeded a configured dataset result limit."
            ) from exc

        self._check_deadline(started, timeout, token)
        page_count = len(pages)
        rendered_pages: list[str] = []
        settings = get_pagination_settings(context)
        for page_index, page_buffer in enumerate(pages):
            bands_html = self._static_bands_html(context, page_index, settings)
            static_html, static_count = self._static_objects_html(
                context, page_index, page_count, settings
            )
            for _ in range(static_count):
                object_count = self._claim_object(object_count)
            rendered_pages.append(
                runtime_page_html(
                    context,
                    page_index + 1,
                    bands_html + "".join(page_buffer.detail_bands),
                    static_html + "".join(page_buffer.detail_objects),
                )
            )

        empty_message = (
            "No rows matched the selected parameters."
            if row_count == 0 and self.policy.show_empty_result_message
            else None
        )
        html = render_runtime_document(context, rendered_pages, empty_message=empty_message)
        if len(html.encode("utf-8")) > self.policy.max_html_bytes:
            raise RuntimeReportLimitError(
                "Report preview exceeded the configured output-size limit."
            )
        elapsed_ms = max(0.0, (monotonic() - started) * 1000.0)
        warnings = self._warnings(execution_summary, max_rows)
        summary = RuntimePreviewSummary(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            row_count=row_count,
            page_count=page_count,
            rendered_object_count=object_count,
            truncated=bool(getattr(execution_summary, "truncated", False)),
            cancelled=False,
            elapsed_ms=elapsed_ms,
            warnings=warnings,
        )
        logger.info(
            "Live report preview completed for dataset %s: rows=%d, pages=%d, "
            "truncated=%s, elapsed_ms=%.3f.",
            dataset.id,
            row_count,
            page_count,
            summary.truncated,
            elapsed_ms,
        )
        return RuntimePreviewResult(html=html, summary=summary)

    def _layout(self, report: Report, context: RenderContext, dataset_id: str) -> _Layout:
        domain_detail = next(
            (
                band
                for band in report.bands
                if (band.id.casefold() == "detail" or band.type.casefold() == "detail")
                and band.dataset_id in (None, dataset_id)
            ),
            None,
        )
        render_detail = next(
            (band for band in context.bands if band.id == getattr(domain_detail, "id", "")),
            None,
        )
        if domain_detail is None or render_detail is None:
            raise RuntimeBandConfigurationError(
                "The Detail band is not configured for the selected dataset."
            )
        render_by_id = {item.id: item for item in context.objects}
        detail_objects = [
            (item, render_by_id[item.id])
            for item in report.objects
            if item.band_id == domain_detail.id and item.id in render_by_id
        ]
        factor = convert_unit(1.0, context.page.unit, "px")
        origin_px = render_detail.y
        content_extent = max(
            (
                object_px(item, context.page.unit)[1]
                + object_px(item, context.page.unit)[3]
                - origin_px
                for _, item in detail_objects
            ),
            default=0.0,
        )
        configured = domain_detail.repeat.get("row_height") if domain_detail.repeat else None
        domain_height_px = max(float(domain_detail.height) * factor, 0.0)
        available_height = max(render_detail.height, 0.0)
        if configured is not None:
            row_height = float(configured) * factor
        elif domain_height_px > available_height * 0.5 and content_extent > 0:
            row_height = content_extent
        else:
            row_height = domain_height_px or content_extent
        if row_height <= 0:
            raise RuntimeBandConfigurationError("The Detail band height must be positive.")
        margin = report.page.margin
        content_top = max(origin_px, convert_unit(float(margin.top), context.page.unit, "px"))
        footer = next((band for band in context.bands if band.id == "page_footer"), None)
        content_bottom = footer.y if footer is not None else context.page.height_px
        content_bottom = min(
            content_bottom,
            context.page.height_px
            - convert_unit(float(margin.bottom), context.page.unit, "px"),
        )
        printable = content_bottom - content_top
        if row_height > printable or printable <= 0:
            raise RuntimeBandConfigurationError(
                "The Detail band is taller than the printable page area."
            )
        return _Layout(
            detail_objects=detail_objects,
            detail_render_band=render_detail,
            detail_origin_px=origin_px,
            content_top_px=content_top,
            row_height_px=row_height,
            rows_per_page=max(1, int(printable // row_height)),
            unit_factor=factor,
        )

    def _render_detail_object(
        self,
        domain_object: Object,
        render_object: RenderObject,
        row: object,
        dataset: object,
        context: RenderContext,
        row_y_px: float,
        origin_px: float,
        row_index: int,
    ) -> str:
        resolved = render_object
        binding = domain_object.dataset_binding
        if binding is not None:
            value = self.binding_resolver.resolve(binding, dataset=dataset, row=row)
            field: DatasetField = next(
                item for item in dataset.fields if item.name == binding.field_name
            )
            text = self.value_formatter.format_value(
                value, field=field, report_object=domain_object
            )
            resolved = replace(resolved, text=text, binding="", formula="", formula_mode=False)
        x_px, y_px, width_px, height_px = object_px(resolved, context.page.unit)
        del x_px, width_px, height_px
        flowed_y_px = row_y_px + (y_px - origin_px)
        resolved = replace(
            resolved,
            id=f"{resolved.id}__row_{row_index}",
            y=flowed_y_px / convert_unit(1.0, context.page.unit, "px"),
        )
        return render_html_object(resolved, context)

    @staticmethod
    def _row_context(context: RenderContext, values: Mapping[str, object]) -> RenderContext:
        return RenderContext(
            report=context.report,
            data={**dict(context.data), "__slim_row__": values},
            page=context.page,
            bands=context.bands,
            objects=context.objects,
            title=context.title,
            asset_provider=context.asset_provider,
            asset_resolver=context.asset_resolver,
        )

    @staticmethod
    def _detail_band_html(
        band: object, y: float, row_height: float, row_index: int
    ) -> str:
        return render_html_band(
            replace(band, id=f"{band.id}__row_{row_index}", y=y, height=row_height)
        )

    @staticmethod
    def _static_bands_html(
        context: RenderContext, page_index: int, settings: Mapping[str, bool]
    ) -> str:
        rendered = []
        for band in context.bands:
            if band.id == "detail":
                continue
            if band.id == "page_header" and page_index and not settings["repeat_page_header"]:
                continue
            if band.id == "page_footer" and page_index and not settings["repeat_page_footer"]:
                continue
            if band.id not in {"page_header", "page_footer"} and page_index:
                continue
            rendered.append(render_html_band(band))
        return "".join(rendered)

    @staticmethod
    def _static_objects_html(
        context: RenderContext,
        page_index: int,
        total_pages: int,
        settings: Mapping[str, bool],
    ) -> tuple[str, int]:
        rendered = []
        count = 0
        page_context = context_with_page_numbers(context, page_index + 1, total_pages)
        for item in context.objects:
            if item.band == "detail":
                continue
            if item.band == "page_header" and page_index and not settings["repeat_page_header"]:
                continue
            if item.band == "page_footer" and page_index and not settings["repeat_page_footer"]:
                continue
            if item.band not in {"page_header", "page_footer"} and page_index:
                continue
            rendered.append(render_html_object(item, page_context))
            count += 1
        return "".join(rendered), count

    def _claim_object(self, current: int) -> int:
        if current >= self.policy.max_rendered_objects:
            raise RuntimeReportLimitError(
                "Report preview exceeded the configured rendered-object limit."
            )
        return current + 1

    @staticmethod
    def _check_deadline(
        started: float,
        timeout_seconds: int,
        token: DatasetExecutionCancellationToken,
    ) -> None:
        if token.is_cancelled:
            raise RuntimePreviewCancelledError("Report preview was cancelled.")
        if monotonic() - started > timeout_seconds:
            token.cancel()
            raise RuntimePreviewTimeoutError("Report preview timed out.")

    @staticmethod
    def _effective_limit(name: str, requested: int | None, maximum: int) -> int:
        if requested is not None and requested > maximum:
            raise ValueError(f"{name} exceeds the configured preview limit of {maximum}.")
        return requested or maximum

    def _warnings(self, summary: object, max_rows: int) -> tuple[RuntimePreviewWarning, ...]:
        warnings: list[RuntimePreviewWarning] = []
        if bool(getattr(summary, "truncated", False)):
            warnings.append(
                RuntimePreviewWarning(
                    "preview_truncated", f"Preview is limited to {max_rows} rows."
                )
            )
        if self.policy.include_execution_warnings:
            for message in getattr(summary, "warnings", ()):
                if "configured limit" not in str(message):
                    warnings.append(RuntimePreviewWarning("execution_warning", str(message)))
        return tuple(warnings)


@dataclass(frozen=True)
class _Layout:
    detail_objects: list[tuple[Object, RenderObject]]
    detail_render_band: object
    detail_origin_px: float
    content_top_px: float
    row_height_px: float
    rows_per_page: int
    unit_factor: float

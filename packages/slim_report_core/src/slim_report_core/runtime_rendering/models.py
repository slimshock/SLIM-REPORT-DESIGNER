"""Immutable public contracts for live report previews."""

from __future__ import annotations

from dataclasses import dataclass

from ..data_sources import ReportDataset
from ..dataset_execution import DatasetExecutionSchema, DatasetRow
from ..report import Report


def _positive_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


@dataclass(frozen=True)
class RuntimePreviewPolicy:
    """Shared fail-closed limits for Designer live previews."""

    max_rows: int = 500
    max_pages: int = 100
    max_rendered_objects: int = 100_000
    max_html_bytes: int = 20_971_520
    max_elapsed_seconds: int = 30
    stop_on_missing_binding: bool = True
    stop_on_unsupported_binding: bool = True
    show_empty_result_message: bool = True
    include_execution_warnings: bool = True
    include_render_warnings: bool = True

    def __post_init__(self) -> None:
        for name in (
            "max_rows",
            "max_pages",
            "max_rendered_objects",
            "max_html_bytes",
            "max_elapsed_seconds",
        ):
            _positive_integer(getattr(self, name), name)
        for name in (
            "stop_on_missing_binding",
            "stop_on_unsupported_binding",
            "show_empty_result_message",
            "include_execution_warnings",
            "include_render_warnings",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean.")


@dataclass(frozen=True)
class RuntimePreviewOptions:
    """Optional stricter settings for one preview."""

    dataset_id: str | None = None
    max_rows: int | None = None
    timeout_seconds: int | None = None
    include_debug_metadata: bool = False

    def __post_init__(self) -> None:
        if self.dataset_id is not None:
            dataset_id = str(self.dataset_id).strip()
            if not dataset_id:
                raise ValueError("dataset_id must not be empty.")
            object.__setattr__(self, "dataset_id", dataset_id)
        for name in ("max_rows", "timeout_seconds"):
            value = getattr(self, name)
            if value is not None:
                _positive_integer(value, name)
        if not isinstance(self.include_debug_metadata, bool):
            raise ValueError("include_debug_metadata must be a boolean.")


@dataclass(frozen=True)
class RuntimePreviewWarning:
    code: str
    message: str


@dataclass(frozen=True)
class RuntimePreviewSummary:
    dataset_id: str
    dataset_name: str
    row_count: int
    page_count: int
    rendered_object_count: int
    truncated: bool
    cancelled: bool
    elapsed_ms: float
    warnings: tuple[RuntimePreviewWarning, ...] = ()

    def __post_init__(self) -> None:
        if min(self.row_count, self.page_count, self.rendered_object_count) < 0:
            raise ValueError("Preview summary counts must not be negative.")
        if self.elapsed_ms < 0:
            raise ValueError("Preview summary elapsed_ms must not be negative.")
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class RuntimePreviewResult:
    html: str
    summary: RuntimePreviewSummary


@dataclass(frozen=True)
class RuntimeRenderContext:
    """Read-only context for static content or one current Detail row."""

    report: Report
    dataset: ReportDataset
    execution_schema: DatasetExecutionSchema
    row: DatasetRow | None
    row_index: int | None
    page_number: int
    total_pages: int | None = None

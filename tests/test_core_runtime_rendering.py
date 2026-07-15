from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import pytest

from slim_report_core import (
    Band,
    DatasetExecutionCancellationToken,
    DatasetExecutionField,
    DatasetExecutionPolicy,
    DatasetExecutionSchema,
    DatasetExecutionSummary,
    DatasetField,
    DatasetFieldBinding,
    DatasetRow,
    Margin,
    MySQLConnectionConfig,
    Object,
    Page,
    Report,
    ReportDataset,
    ReportDataSource,
    RuntimeBindingResolutionError,
    RuntimeBindingResolver,
    RuntimePreviewCancelledError,
    RuntimePreviewOptions,
    RuntimePreviewPolicy,
    RuntimeReportLimitError,
    RuntimeReportRenderService,
    RuntimeUnsupportedBindingError,
    RuntimeValueFormatter,
    TextObject,
)
from slim_report_core.serialization import JSONSerializer


class FakeStream:
    def __init__(
        self,
        rows: list[DatasetRow],
        *,
        truncated: bool = False,
    ) -> None:
        self.schema = DatasetExecutionSchema(
            "patients",
            "Patients",
            (DatasetExecutionField("name", "string", True, 1),),
        )
        self._rows = iter(rows)
        self._row_count = 0
        self._truncated = truncated
        self.closed = False

    def __iter__(self) -> FakeStream:
        return self

    def __next__(self) -> DatasetRow:
        row = next(self._rows)
        self._row_count += 1
        return row

    def __enter__(self) -> FakeStream:
        return self

    def __exit__(self, *args: object) -> None:
        del args
        self.closed = True

    def summary(self) -> DatasetExecutionSummary:
        return DatasetExecutionSummary(
            dataset_id="patients",
            dataset_name="Patients",
            provider="mysql",
            row_count=self._row_count,
            field_count=1,
            truncated=self._truncated,
            cancelled=False,
            elapsed_ms=1.0,
        )


class FakeExecutionService:
    policy = DatasetExecutionPolicy()

    def __init__(self, stream: FakeStream) -> None:
        self.stream = stream
        self.open_count = 0
        self.options = None

    def resolve_primary_dataset(self, report: Report, dataset_id: str | None = None) -> Any:
        return report.get_dataset(dataset_id or "patients")

    def open_dataset(self, report: Report, dataset_id: str, **kwargs: object) -> FakeStream:
        del report, dataset_id
        self.open_count += 1
        self.options = kwargs["options"]
        return self.stream


def live_report(*, field_name: str = "name") -> Report:
    source = ReportDataSource(
        id="mysql",
        name="MySQL",
        type="mysql",
        connection=MySQLConnectionConfig(
            database="lis",
            username="reader",
            password="runtime-only",
        ),
    )
    dataset = ReportDataset(
        id="patients",
        name="Patients",
        data_source_id="mysql",
        source_type="query",
        query="SELECT name FROM report_patients",
        fields=[DatasetField(name="name", data_type="string", nullable=True)],
    )
    report = Report(
        page=Page(
            width=300,
            height=240,
            unit="px",
            margin=Margin(top=10, right=10, bottom=10, left=10),
        ),
        bands=[
            Band("page_header", "page_header", y=0, height=40),
            Band("detail", "detail", y=40, height=30, dataset_id="patients"),
            Band("page_footer", "page_footer", y=200, height=40),
        ],
        data_sources=[source],
        datasets=[dataset],
    )
    report.add_object(TextObject("Patients", id="title", y=8, height=20, band_id="page_header"))
    bound = TextObject(
        "PLACEHOLDER MUST NOT RENDER",
        id="patient_name",
        x=10,
        y=44,
        width=180,
        height=20,
        band_id="detail",
    )
    bound.dataset_binding = DatasetFieldBinding("patients", field_name)
    report.add_object(bound)
    report.add_object(TextObject("Static", id="static", x=200, y=44, height=20, band_id="detail"))
    report.add_object(TextObject("Footer", id="footer", y=210, height=20, band_id="page_footer"))
    return report


def render(rows: list[dict[str, object]], **kwargs: object) -> tuple[Any, FakeExecutionService]:
    stream = FakeStream(
        [DatasetRow(index, values) for index, values in enumerate(rows, start=1)],
        truncated=bool(kwargs.pop("truncated", False)),
    )
    execution = FakeExecutionService(stream)
    result = RuntimeReportRenderService(
        execution_service=execution,
        policy=kwargs.pop("policy", None),
    ).render_html(live_report(), **kwargs)
    return result, execution


def test_preview_policy_and_options_reject_invalid_or_relaxed_limits() -> None:
    with pytest.raises(ValueError):
        RuntimePreviewPolicy(max_rows=True)
    with pytest.raises(ValueError):
        RuntimePreviewOptions(max_rows=0)
    service = RuntimeReportRenderService(
        execution_service=FakeExecutionService(FakeStream([])),
        policy=RuntimePreviewPolicy(max_rows=5),
    )
    with pytest.raises(ValueError, match="configured preview limit"):
        service.render_html(live_report(), options=RuntimePreviewOptions(max_rows=6))


def test_binding_resolver_is_exact_and_rejects_cross_dataset_and_missing_rows() -> None:
    report = live_report()
    dataset = report.datasets[0]
    resolver = RuntimeBindingResolver()
    assert resolver.resolve(
        DatasetFieldBinding("patients", "name"),
        dataset=dataset,
        row=DatasetRow(1, {"name": "Alice"}),
    ) == "Alice"
    with pytest.raises(RuntimeBindingResolutionError):
        resolver.resolve(
            DatasetFieldBinding("patients", "name"),
            dataset=dataset,
            row=DatasetRow(1, {"Name": "Alice"}),
        )
    with pytest.raises(RuntimeBindingResolutionError):
        resolver.resolve(
            DatasetFieldBinding("other", "name"),
            dataset=dataset,
            row=DatasetRow(1, {"name": "Alice"}),
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("text", "text"),
        (False, "False"),
        (12, "12"),
        (1.25, "1.25"),
        (Decimal("1.2300"), "1.2300"),
        (date(2026, 1, 2), "2026-01-02"),
        (time(3, 4, 5), "03:04:05"),
        (datetime(2026, 1, 2, 3, 4, 5), "2026-01-02 03:04:05"),
    ],
)
def test_value_formatter_supports_safe_scalars(value: object, expected: str) -> None:
    field = DatasetField(name="name", data_type="string", nullable=True)
    report_object = TextObject("", id="value")
    assert RuntimeValueFormatter().format_value(
        value, field=field, report_object=report_object
    ) == expected


def test_value_formatter_rejects_binary_nonfinite_and_unsupported_objects() -> None:
    formatter = RuntimeValueFormatter()
    field = DatasetField(name="name", data_type="string", nullable=True)
    with pytest.raises(RuntimeUnsupportedBindingError):
        formatter.format_value(b"secret", field=field, report_object=TextObject("", id="x"))
    with pytest.raises(RuntimeUnsupportedBindingError):
        formatter.format_value(float("inf"), field=field, report_object=TextObject("", id="x"))
    with pytest.raises(RuntimeUnsupportedBindingError):
        formatter.format_value("x", field=field, report_object=Object("x", "image"))


def test_runtime_preview_streams_rows_escapes_html_and_preserves_order() -> None:
    result, execution = render(
        [
            {"name": '<script>alert("x")</script> & Jose'},
            {"name": "Bob\n<b>bold</b>"},
        ]
    )
    assert result.summary.row_count == 2
    assert result.html.index("&lt;script&gt;") < result.html.index("Bob\n&lt;b&gt;bold&lt;/b&gt;")
    assert "<script>alert" not in result.html
    assert "PLACEHOLDER MUST NOT RENDER" not in result.html
    assert result.html.count("Static") == 2
    assert execution.stream.closed


def test_runtime_preview_paginates_and_repeats_header_and_footer() -> None:
    result, _execution = render([{"name": f"Patient {index}"} for index in range(8)])
    assert result.summary.page_count == 2
    assert result.html.count("Patients") == 2
    assert result.html.count("Footer") == 2
    assert result.html.index("Patient 0") < result.html.index("Patient 7")


def test_empty_and_truncated_results_have_safe_preview_metadata() -> None:
    empty, _execution = render([])
    assert empty.summary.row_count == 0
    assert "No rows matched the selected parameters." in empty.html
    truncated, execution = render([{"name": "A"}], truncated=True)
    assert truncated.summary.truncated
    assert truncated.summary.warnings[0].code == "preview_truncated"
    assert execution.options.max_rows == 500


def test_binding_validation_happens_before_execution_and_report_is_immutable() -> None:
    report = live_report(field_name="removed")
    before = JSONSerializer().dump_mapping(report)
    execution = FakeExecutionService(FakeStream([]))
    with pytest.raises(RuntimeBindingResolutionError):
        RuntimeReportRenderService(execution_service=execution).render_html(report)
    assert execution.open_count == 0
    assert JSONSerializer().dump_mapping(report) == before


def test_object_page_and_output_limits_close_stream_without_partial_result() -> None:
    policy = RuntimePreviewPolicy(max_rendered_objects=1)
    execution = FakeExecutionService(FakeStream([DatasetRow(1, {"name": "Alice"})]))
    with pytest.raises(RuntimeReportLimitError, match="rendered-object"):
        RuntimeReportRenderService(execution_service=execution, policy=policy).render_html(
            live_report()
        )
    assert execution.stream.closed


def test_pre_cancelled_preview_opens_no_execution_stream() -> None:
    execution = FakeExecutionService(FakeStream([]))
    token = DatasetExecutionCancellationToken()
    token.cancel()
    with pytest.raises(RuntimePreviewCancelledError):
        RuntimeReportRenderService(execution_service=execution).render_html(
            live_report(), cancellation_token=token
        )
    assert execution.open_count == 0

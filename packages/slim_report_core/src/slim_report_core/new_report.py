"""Framework-independent configuration and builder for new Designer reports."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass

from .bindings import ReportBindingService
from .data_sources import DatasetField, ReportDataset, ReportDataSource
from .exceptions import ReportValidationError
from .models import Band, Margin, Metadata, Page, Style, TextObject
from .report import Report


class NewReportWizardError(ReportValidationError):
    """Base error for new-report configuration and generation failures."""


class InvalidNewReportConfigurationError(NewReportWizardError):
    """Raised when report or page configuration is invalid."""


class InvalidNewReportLayoutError(NewReportWizardError):
    """Raised when the requested initial layout cannot be generated safely."""


class NewReportFieldSelectionError(InvalidNewReportLayoutError):
    """Raised when selected layout fields are invalid or unsupported."""


@dataclass(frozen=True)
class SelectedReportField:
    """One dataset field selected for the generated starting layout."""

    field_name: str
    label: str = ""
    order: int = 0

    def __post_init__(self) -> None:
        field_name = str(self.field_name).strip()
        if not field_name:
            raise NewReportFieldSelectionError("Selected field name must not be empty.")
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(
            self, "label", str(self.label).strip() or friendly_field_label(field_name)
        )
        object.__setattr__(self, "order", int(self.order))


@dataclass(frozen=True)
class NewReportPageConfiguration:
    """Page settings collected by the New Report Wizard."""

    size: str = "A4"
    orientation: str = "portrait"
    margin_top: float = 24.0
    margin_right: float = 24.0
    margin_bottom: float = 24.0
    margin_left: float = 24.0
    width: float | None = None
    height: float | None = None
    unit: str = "px"


@dataclass(frozen=True)
class NewReportDataConfiguration:
    """Optional MySQL data-source and dataset configuration."""

    data_source: ReportDataSource
    dataset: ReportDataset

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_source", copy.deepcopy(self.data_source))
        object.__setattr__(self, "dataset", copy.deepcopy(self.dataset))


@dataclass(frozen=True)
class NewReportLayoutConfiguration:
    """Initial blank or tabular canvas layout settings."""

    layout_type: str = "blank"
    selected_fields: tuple[SelectedReportField, ...] = ()
    include_title: bool = True
    include_column_headers: bool = True
    allow_narrow_columns: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "layout_type", str(self.layout_type).strip().lower())
        object.__setattr__(self, "selected_fields", tuple(self.selected_fields))


@dataclass(frozen=True)
class NewReportConfiguration:
    """Complete authoritative input for one atomic new-report build."""

    report_name: str
    page: NewReportPageConfiguration = NewReportPageConfiguration()
    layout: NewReportLayoutConfiguration = NewReportLayoutConfiguration()
    description: str | None = None
    data: NewReportDataConfiguration | None = None

    def __post_init__(self) -> None:
        name = str(self.report_name).strip()
        if not name:
            raise InvalidNewReportConfigurationError("Report name is required.")
        object.__setattr__(self, "report_name", name)
        description = None if self.description is None else str(self.description).strip() or None
        object.__setattr__(self, "description", description)
        if self.data is not None:
            object.__setattr__(self, "data", copy.deepcopy(self.data))


class NewReportWizardBuilder:
    """Validate new-report configuration and build a complete Report once."""

    minimum_column_width = 48.0

    def build(self, configuration: NewReportConfiguration) -> Report:
        """Return a new report without mutating any existing report."""
        page = self._build_page(configuration.page)
        self._validate_data(configuration.data)
        selected = self._validate_layout(configuration)
        bands = self._build_bands(page, configuration.layout)
        report = Report(
            metadata=Metadata(
                title=configuration.report_name,
                description=configuration.description,
            ),
            page=page,
            bands=bands,
            data_sources=(
                [copy.deepcopy(configuration.data.data_source)] if configuration.data else []
            ),
            datasets=([copy.deepcopy(configuration.data.dataset)] if configuration.data else []),
        )
        if configuration.layout.layout_type == "tabular":
            self._build_tabular_objects(report, configuration, selected)

        validation = report.validate()
        if not validation.is_valid:
            raise InvalidNewReportConfigurationError(validation.errors[0].message)
        binding_validation = ReportBindingService().validate(report)
        if not binding_validation.valid:
            raise InvalidNewReportLayoutError(binding_validation.issues[0].message)
        json.dumps(report.template.to_dict())
        return report

    def warnings(self, configuration: NewReportConfiguration) -> tuple[str, ...]:
        """Return non-secret layout warnings without constructing a report."""
        page = self._build_page(configuration.page)
        selected = self._validate_layout(configuration, enforce_width=False)
        warnings: list[str] = []
        if configuration.layout.layout_type == "tabular" and selected:
            printable_width = page.width - page.margin.left - page.margin.right
            if printable_width / len(selected) < self.minimum_column_width:
                warnings.append(
                    f"{len(selected)} selected fields may not fit readably on "
                    f"{configuration.page.size} {configuration.page.orientation}."
                )
        if configuration.data:
            unknown = [
                field.name
                for field in configuration.data.dataset.fields
                if field.data_type in {"binary", "unknown"}
            ]
            if unknown:
                warnings.append(
                    f"{len(unknown)} dataset fields cannot be inserted directly as text."
                )
        return tuple(warnings)

    def _build_page(self, config: NewReportPageConfiguration) -> Page:
        size = str(config.size).strip().lower()
        orientation = str(config.orientation).strip().lower()
        unit = str(config.unit).strip().lower()
        if size not in {"a4", "letter", "legal", "custom"}:
            raise InvalidNewReportConfigurationError(f"Unsupported page size: {config.size}.")
        if orientation not in {"portrait", "landscape"}:
            raise InvalidNewReportConfigurationError(
                f"Unsupported page orientation: {config.orientation}."
            )
        if unit != "px":
            raise InvalidNewReportConfigurationError("The New Report Wizard uses page unit 'px'.")
        dimensions = {
            "a4": (595.0, 842.0),
            "letter": (612.0, 792.0),
            "legal": (612.0, 1008.0),
        }
        if size == "custom":
            width = float(config.width or 0)
            height = float(config.height or 0)
        else:
            width, height = dimensions[size]
        if orientation == "landscape" and width < height:
            width, height = height, width
        elif orientation == "portrait" and width > height:
            width, height = height, width
        if width <= 0 or height <= 0:
            raise InvalidNewReportConfigurationError("Page width and height must be positive.")
        margins = tuple(
            float(value)
            for value in (
                config.margin_top,
                config.margin_right,
                config.margin_bottom,
                config.margin_left,
            )
        )
        if any(value < 0 for value in margins):
            raise InvalidNewReportConfigurationError("Page margins must not be negative.")
        top, right, bottom, left = margins
        if left + right >= width or top + bottom >= height:
            raise InvalidNewReportConfigurationError("Page margins leave no printable report area.")
        return Page(
            id="page_1",
            size=config.size,
            orientation=orientation,
            unit=unit,
            width=width,
            height=height,
            margin=Margin(top=top, right=right, bottom=bottom, left=left),
        )

    @staticmethod
    def _validate_data(data: NewReportDataConfiguration | None) -> None:
        if data is None:
            return
        if data.data_source.type != "mysql":
            raise InvalidNewReportConfigurationError(
                "The New Report Wizard currently supports MySQL data sources only."
            )
        if data.dataset.data_source_id != data.data_source.id:
            raise InvalidNewReportConfigurationError(
                "The dataset does not reference the configured data source."
            )

    def _validate_layout(
        self,
        configuration: NewReportConfiguration,
        *,
        enforce_width: bool = True,
    ) -> tuple[tuple[SelectedReportField, DatasetField], ...]:
        layout = configuration.layout
        if layout.layout_type not in {"blank", "tabular"}:
            raise InvalidNewReportLayoutError(
                f"Unsupported new report layout: {layout.layout_type}."
            )
        if layout.layout_type == "blank":
            return ()
        if configuration.data is None:
            raise InvalidNewReportLayoutError("Tabular layout requires a configured dataset.")
        if not layout.selected_fields:
            raise NewReportFieldSelectionError(
                "Tabular layout requires at least one selected dataset field."
            )
        fields = {field.name: field for field in configuration.data.dataset.fields}
        seen: set[str] = set()
        selected: list[tuple[SelectedReportField, DatasetField]] = []
        for item in sorted(layout.selected_fields, key=lambda value: value.order):
            if item.field_name in seen:
                raise NewReportFieldSelectionError(
                    f"The field {item.field_name!r} was selected more than once."
                )
            seen.add(item.field_name)
            field = fields.get(item.field_name)
            if field is None:
                raise NewReportFieldSelectionError(
                    f"The selected field {item.field_name!r} does not exist in dataset "
                    f"{configuration.data.dataset.name!r}."
                )
            if field.data_type in {"binary", "unknown"}:
                raise NewReportFieldSelectionError(
                    f"The field {item.field_name!r} cannot be inserted directly as text."
                )
            selected.append((item, field))
        if enforce_width and not layout.allow_narrow_columns:
            page = self._build_page(configuration.page)
            printable_width = page.width - page.margin.left - page.margin.right
            if printable_width / len(selected) < self.minimum_column_width:
                raise InvalidNewReportLayoutError(
                    "Selected fields do not fit readable columns on the configured page."
                )
        return tuple(selected)

    @staticmethod
    def _build_bands(page: Page, layout: NewReportLayoutConfiguration) -> list[Band]:
        if layout.layout_type == "tabular":
            header_height = 82.0 if layout.include_title and layout.include_column_headers else 52.0
            if not layout.include_title and not layout.include_column_headers:
                header_height = 32.0
            detail_height = 32.0
            footer_height = 40.0
        else:
            header_height = min(100.0, max(60.0, round(page.height * 0.12)))
            footer_height = min(60.0, max(40.0, round(page.height * 0.07)))
            detail_height = max(80.0, page.height - header_height - footer_height)
        return [
            Band(
                id="page_header",
                type="page_header",
                name="Page Header",
                y=0,
                height=header_height,
            ),
            Band(
                id="detail",
                type="detail",
                name="Detail",
                y=header_height,
                height=detail_height,
            ),
            Band(
                id="page_footer",
                type="page_footer",
                name="Page Footer",
                y=header_height + detail_height,
                height=footer_height,
            ),
        ]

    def _build_tabular_objects(
        self,
        report: Report,
        configuration: NewReportConfiguration,
        selected: tuple[tuple[SelectedReportField, DatasetField], ...],
    ) -> None:
        layout = configuration.layout
        dataset = configuration.data.dataset
        page = report.page
        widths = calculate_column_widths(
            page.width - page.margin.left - page.margin.right,
            tuple(field for _, field in selected),
            minimum=self.minimum_column_width,
            allow_narrow=layout.allow_narrow_columns,
        )
        header = next(band for band in report.bands if band.id == "page_header")
        detail = next(band for band in report.bands if band.id == "detail")
        if layout.include_title:
            report.add_object(
                TextObject(
                    configuration.report_name,
                    id="report_title",
                    x=page.margin.left,
                    y=max(6.0, page.margin.top / 2),
                    width=page.width - page.margin.left - page.margin.right,
                    height=28.0,
                    band_id=header.id,
                    style=Style(font_size=18, bold=True, align="left", vertical_align="middle"),
                    properties={"name": "report_title"},
                )
            )
        header_y = 46.0 if layout.include_title else 12.0
        detail_y = detail.y + 4.0
        x = page.margin.left
        binding_service = ReportBindingService()
        used_ids = {item.id for item in report.objects}
        for (selection, field), width in zip(selected, widths, strict=True):
            suffix = _safe_identifier(field.name)
            if layout.include_column_headers:
                header_id = _unique_id(f"header_{suffix}", used_ids)
                report.add_object(
                    TextObject(
                        selection.label,
                        id=header_id,
                        x=x,
                        y=header_y,
                        width=width,
                        height=24.0,
                        band_id=header.id,
                        style=Style(
                            font_size=11,
                            bold=True,
                            align=_field_alignment(field.data_type),
                            vertical_align="middle",
                            background_color="#f3f4f6",
                            border_width=1,
                            border_color="#d1d5db",
                        ),
                        properties={"name": header_id},
                    )
                )
            detail_id = _unique_id(f"field_{suffix}", used_ids)
            report.add_object(
                TextObject(
                    field.name,
                    id=detail_id,
                    x=x,
                    y=detail_y,
                    width=width,
                    height=24.0,
                    band_id=detail.id,
                    style=Style(
                        font_size=11,
                        align=_field_alignment(field.data_type),
                        vertical_align="middle",
                    ),
                    properties={"name": detail_id},
                )
            )
            binding_service.bind_object(report, detail_id, dataset.id, field.name)
            x += width


def friendly_field_label(field_name: str) -> str:
    """Return a deterministic friendly label without changing the field name."""
    acronyms = {"dob": "DOB", "hgb": "HGB", "id": "ID", "pid": "PID", "wbc": "WBC"}
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(field_name)).replace("-", " ")
    return " ".join(
        acronyms.get(word.casefold(), word[:1].upper() + word[1:])
        for word in words.split("_")
        for word in word.split()
    )


def calculate_column_widths(
    available_width: float,
    fields: tuple[DatasetField, ...],
    *,
    minimum: float = 48.0,
    maximum: float = 240.0,
    allow_narrow: bool = False,
) -> tuple[float, ...]:
    """Distribute printable width deterministically across selected fields."""
    if not fields or available_width <= 0:
        raise InvalidNewReportLayoutError("Column layout requires positive printable width.")
    effective_minimum = minimum
    if len(fields) * minimum > available_width:
        if not allow_narrow:
            raise InvalidNewReportLayoutError(
                "Selected fields do not fit readable columns on the configured page."
            )
        effective_minimum = max(1.0, available_width / len(fields))
    weights = tuple(_field_weight(field) for field in fields)
    widths = [available_width * weight / sum(weights) for weight in weights]
    widths = [min(maximum, max(effective_minimum, width)) for width in widths]
    for _ in range(len(widths) * 2):
        difference = available_width - sum(widths)
        if abs(difference) < 0.001:
            break
        adjustable = [
            index
            for index, width in enumerate(widths)
            if (difference > 0 and width < maximum)
            or (difference < 0 and width > effective_minimum)
        ]
        if not adjustable:
            break
        share = difference / len(adjustable)
        for index in adjustable:
            widths[index] = min(maximum, max(effective_minimum, widths[index] + share))
    difference = available_width - sum(widths)
    widths[-1] += difference
    return tuple(widths)


def _field_weight(field: DatasetField) -> float:
    weights = {
        "string": 2.0,
        "datetime": 1.6,
        "date": 1.2,
        "time": 1.1,
        "decimal": 1.1,
        "float": 1.1,
        "integer": 1.0,
        "boolean": 0.8,
    }
    length_factor = min(0.6, max(0.0, (len(field.label or field.name) - 10) / 40))
    return weights.get(field.data_type, 1.2) + length_factor


def _field_alignment(data_type: str) -> str:
    if data_type in {"integer", "float", "decimal", "number"}:
        return "right"
    if data_type == "boolean":
        return "center"
    return "left"


def _safe_identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return normalized or "field"


def _unique_id(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate

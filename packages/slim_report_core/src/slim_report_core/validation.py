"""Structured validation for report domain models."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .models import Asset, Band, Layer, Object, Page, Style

SUPPORTED_PAGE_SIZES = {"a4", "letter"}
SUPPORTED_PAGE_UNITS = {"px", "pt", "in", "mm", "cm"}
SUPPORTED_PAGE_ORIENTATIONS = {"portrait", "landscape"}
SUPPORTED_OBJECT_TYPES = {
    "barcode",
    "field",
    "image",
    "line",
    "qrcode",
    "rectangle",
    "table",
    "text",
}
SAFE_FUNCTIONS = {"today", "now"}

_TEXT_EXPRESSION_PATTERN = re.compile(r"\{\{\s*(.*?)\s*\}\}")


@dataclass(frozen=True)
class ReportValidationIssue:
    """A structured report validation issue."""

    code: str
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible issue dictionary."""
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class ReportValidationResult:
    """Validation result returned by ``Report.validate()``."""

    errors: list[ReportValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True when there are no validation errors."""
        return not self.errors

    def add_error(self, code: str, path: str, message: str) -> None:
        """Add an error to this result."""
        self.errors.append(ReportValidationIssue(code=code, path=path, message=message))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible validation result."""
        return {
            "valid": self.is_valid,
            "errors": [error.to_dict() for error in self.errors],
        }


def validate_report(report: Any) -> ReportValidationResult:
    """Validate a report domain model without raising for validation failures."""
    result = ReportValidationResult()

    _validate_pages(report, result)
    _validate_bands(report, result)
    _validate_layers(report, result)
    _validate_styles(report, result)
    _validate_assets(report, result)
    _validate_objects(report, result)

    return result


def _validate_pages(report: Any, result: ReportValidationResult) -> None:
    pages = getattr(report, "pages", None)
    if not isinstance(pages, list) or not pages:
        result.add_error("page.required", "pages", "Report must contain at least one page.")
        return

    seen_ids: set[str] = set()
    for index, page in enumerate(pages):
        path = f"pages[{index}]"
        if not isinstance(page, Page):
            result.add_error("page.invalid", path, "Page must be a Page domain object.")
            continue

        if page.id:
            _validate_unique_id(page.id, seen_ids, result, f"{path}.id", "page.id.duplicate")

        page_size = str(page.size).lower() if page.size is not None else None
        page_unit = str(page.unit).lower()
        page_orientation = str(page.orientation).lower()

        if page_size is not None and page_size not in SUPPORTED_PAGE_SIZES:
            result.add_error(
                "page.size.unsupported",
                f"{path}.size",
                f"Unsupported page size: {page.size}.",
            )
        if page_unit not in SUPPORTED_PAGE_UNITS:
            result.add_error(
                "page.unit.unsupported",
                f"{path}.unit",
                f"Unsupported page unit: {page.unit}.",
            )
        if page_orientation not in SUPPORTED_PAGE_ORIENTATIONS:
            result.add_error(
                "page.orientation.unsupported",
                f"{path}.orientation",
                f"Unsupported page orientation: {page.orientation}.",
            )
        if not _is_positive_number(page.width):
            result.add_error("page.width.invalid", f"{path}.width", "Page width must be positive.")
        if not _is_positive_number(page.height):
            result.add_error(
                "page.height.invalid",
                f"{path}.height",
                "Page height must be positive.",
            )
        for margin_name in ("top", "right", "bottom", "left"):
            margin_value = getattr(page.margin, margin_name, None)
            if not _is_non_negative_number(margin_value):
                result.add_error(
                    "page.margin.invalid",
                    f"{path}.margin.{margin_name}",
                    "Page margins must be non-negative numbers.",
                )


def _validate_objects(report: Any, result: ReportValidationResult) -> None:
    objects = getattr(report, "objects", None)
    if not isinstance(objects, list):
        result.add_error("objects.invalid", "objects", "Report objects must be a list.")
        return

    seen_ids: set[str] = set()
    band_ids = _id_set(getattr(report, "bands", []))
    layer_ids = _id_set(getattr(report, "layers", []))

    for index, obj in enumerate(objects):
        path = f"objects[{index}]"
        if not isinstance(obj, Object):
            result.add_error(
                "object.invalid",
                path,
                "Report object must be an Object domain model.",
            )
            continue

        if not _has_text(obj.id):
            result.add_error("object.id.required", f"{path}.id", "Report object id is required.")
        else:
            _validate_unique_id(obj.id, seen_ids, result, f"{path}.id", "object.id.duplicate")

        if not _has_text(obj.type):
            result.add_error(
                "object.type.required",
                f"{path}.type",
                "Report object type is required.",
            )
        elif str(obj.type) not in SUPPORTED_OBJECT_TYPES:
            result.add_error(
                "object.type.unsupported",
                f"{path}.type",
                f"Unsupported report object type: {obj.type}.",
            )

        for field_name in ("x", "y", "width", "height"):
            value = getattr(obj, field_name)
            if field_name in {"width", "height"}:
                valid = _is_non_negative_number(value)
                message = f"Object {field_name} must be a non-negative number."
            else:
                valid = _is_number(value)
                message = f"Object {field_name} must be a number."
            if not valid:
                result.add_error(
                    f"object.{field_name}.invalid",
                    f"{path}.{field_name}",
                    message,
                )

        if obj.band_id and obj.band_id not in band_ids:
            result.add_error(
                "object.band_id.missing",
                f"{path}.band_id",
                f"Object references missing band: {obj.band_id}.",
            )
        if obj.layer_id and obj.layer_id not in layer_ids:
            result.add_error(
                "object.layer_id.missing",
                f"{path}.layer_id",
                f"Object references missing layer: {obj.layer_id}.",
            )

        _validate_object_binding(obj, result, path)
        _validate_style(obj.style, result, f"{path}.style")


def _validate_object_binding(
    obj: Object,
    result: ReportValidationResult,
    path: str,
) -> None:
    if obj.type == "field":
        expression = getattr(obj.binding, "expression", "") if obj.binding is not None else ""
        if not _has_text(expression):
            result.add_error(
                "binding.required",
                f"{path}.binding",
                "Field objects require a binding expression.",
            )
            return
        _validate_expression(expression, result, f"{path}.binding")
        return

    if obj.type == "text" and obj.text:
        for match_index, match in enumerate(_TEXT_EXPRESSION_PATTERN.finditer(str(obj.text))):
            _validate_expression(
                match.group(1),
                result,
                f"{path}.text.expressions[{match_index}]",
            )


def _validate_bands(report: Any, result: ReportValidationResult) -> None:
    bands = getattr(report, "bands", None)
    if not isinstance(bands, list):
        result.add_error("bands.invalid", "bands", "Report bands must be a list.")
        return

    seen_ids: set[str] = set()
    for index, band in enumerate(bands):
        path = f"bands[{index}]"
        if not isinstance(band, Band):
            result.add_error("band.invalid", path, "Band must be a Band domain object.")
            continue
        if not _has_text(band.id):
            result.add_error("band.id.required", f"{path}.id", "Band id is required.")
        else:
            _validate_unique_id(band.id, seen_ids, result, f"{path}.id", "band.id.duplicate")
        if not _has_text(band.type):
            result.add_error("band.type.required", f"{path}.type", "Band type is required.")
        if not _is_non_negative_number(band.height):
            result.add_error(
                "band.height.invalid",
                f"{path}.height",
                "Band height must be a non-negative number.",
            )


def _validate_layers(report: Any, result: ReportValidationResult) -> None:
    layers = getattr(report, "layers", None)
    if not isinstance(layers, list):
        result.add_error("layers.invalid", "layers", "Report layers must be a list.")
        return

    seen_ids: set[str] = set()
    for index, layer in enumerate(layers):
        path = f"layers[{index}]"
        if not isinstance(layer, Layer):
            result.add_error("layer.invalid", path, "Layer must be a Layer domain object.")
            continue
        if not _has_text(layer.id):
            result.add_error("layer.id.required", f"{path}.id", "Layer id is required.")
        else:
            _validate_unique_id(layer.id, seen_ids, result, f"{path}.id", "layer.id.duplicate")
        if not _has_text(layer.name):
            result.add_error("layer.name.required", f"{path}.name", "Layer name is required.")


def _validate_styles(report: Any, result: ReportValidationResult) -> None:
    styles = getattr(report, "styles", None)
    if not isinstance(styles, dict):
        result.add_error("styles.invalid", "styles", "Report styles must be a dictionary.")
        return

    for style_id, style in styles.items():
        path = f"styles.{style_id}"
        if not _has_text(style_id):
            result.add_error("style.id.required", "styles", "Named style id is required.")
        _validate_style(style, result, path)


def _validate_style(style: Any, result: ReportValidationResult, path: str) -> None:
    if not isinstance(style, Style):
        result.add_error("style.invalid", path, "Style must be a Style domain object.")
        return
    if not isinstance(style.values, dict):
        result.add_error("style.values.invalid", path, "Style values must be a dictionary.")
        return

    for key, value in style.resolved_values().items():
        if not _has_text(key):
            result.add_error("style.key.required", path, "Style keys must be non-empty strings.")
            continue
        key_path = f"{path}.{key}"
        if key in {"font_size"} and not _is_positive_number(value):
            result.add_error(
                "style.value.invalid",
                key_path,
                f"Style value {key!r} must be a positive number.",
            )
        elif key in {
            "border_width",
            "line_width",
            "stroke_width",
        } and not _is_non_negative_number(value):
            result.add_error(
                "style.value.invalid",
                key_path,
                f"Style value {key!r} must be a non-negative number.",
            )
        elif key in {"bold", "italic", "underline"} and not isinstance(value, bool):
            result.add_error(
                "style.value.invalid",
                key_path,
                f"Style value {key!r} must be boolean.",
            )
        elif key == "align" and str(value) not in {"left", "center", "right", "justify"}:
            result.add_error(
                "style.value.invalid",
                key_path,
                "Style value 'align' must be left, center, right, or justify.",
            )
        elif key == "vertical_align" and str(value) not in {"top", "middle", "bottom"}:
            result.add_error(
                "style.value.invalid",
                key_path,
                "Style value 'vertical_align' must be top, middle, or bottom.",
            )


def _validate_assets(report: Any, result: ReportValidationResult) -> None:
    assets = getattr(report, "assets", None)
    if not isinstance(assets, list):
        result.add_error("assets.invalid", "assets", "Report assets must be a list.")
        return

    seen_ids: set[str] = set()
    for index, asset in enumerate(assets):
        path = f"assets[{index}]"
        if not isinstance(asset, Asset):
            result.add_error("asset.invalid", path, "Asset must be an Asset domain object.")
            continue
        if not _has_text(asset.id):
            result.add_error("asset.id.required", f"{path}.id", "Asset id is required.")
        else:
            _validate_unique_id(asset.id, seen_ids, result, f"{path}.id", "asset.id.duplicate")
        if not _has_text(asset.type):
            result.add_error("asset.type.required", f"{path}.type", "Asset type is required.")
        if not _has_text(asset.source):
            result.add_error("asset.source.required", f"{path}.source", "Asset source is required.")
        if not isinstance(asset.metadata, dict):
            result.add_error(
                "asset.metadata.invalid",
                f"{path}.metadata",
                "Asset metadata must be a dictionary.",
            )


def _validate_expression(
    expression: str,
    result: ReportValidationResult,
    path: str,
) -> None:
    normalized = _strip_expression_markers(expression)
    if not _has_text(normalized):
        result.add_error("binding.expression.empty", path, "Binding expression cannot be empty.")
        return

    if normalized.endswith("()"):
        function_name = normalized[:-2].strip()
        if function_name not in SAFE_FUNCTIONS:
            result.add_error(
                "binding.expression.unsupported_function",
                path,
                f"Unsupported expression function: {function_name}().",
            )
        return

    if "(" in normalized or ")" in normalized:
        result.add_error(
            "binding.expression.invalid",
            path,
            "Binding expressions only support dotted paths and safe zero-argument functions.",
        )
        return

    for part in normalized.split("."):
        if not _is_safe_path_part(part):
            result.add_error(
                "binding.expression.invalid",
                path,
                f"Invalid binding expression: {normalized}.",
            )
            return


def _strip_expression_markers(expression: str) -> str:
    value = str(expression).strip()
    match = _TEXT_EXPRESSION_PATTERN.fullmatch(value)
    if match:
        return match.group(1).strip()
    return value


def _validate_unique_id(
    value: str,
    seen_ids: set[str],
    result: ReportValidationResult,
    path: str,
    code: str,
) -> None:
    if value in seen_ids:
        result.add_error(code, path, f"Duplicate id: {value}.")
        return
    seen_ids.add(value)


def _id_set(items: Iterable[Any]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        item_id = getattr(item, "id", None)
        if _has_text(item_id):
            ids.add(str(item_id))
    return ids


def _is_safe_path_part(part: str) -> bool:
    return bool(part) and not part.startswith("_") and part.replace("_", "").isalnum()


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and float(value) > 0


def _is_non_negative_number(value: Any) -> bool:
    return _is_number(value) and float(value) >= 0

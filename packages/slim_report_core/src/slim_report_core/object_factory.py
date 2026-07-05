"""Factory for constructing report object domain models consistently."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exceptions import ReportValidationError
from .models import (
    BarcodeObject,
    Binding,
    FieldObject,
    ImageObject,
    LineObject,
    Object,
    Position,
    QRCodeObject,
    RectangleObject,
    Size,
    Style,
    TableObject,
    TextObject,
)
from .utils import ensure_mapping


class ObjectFactory:
    """Create concrete report objects from APIs, serializers, and integrations."""

    def create_text(
        self,
        text: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 24.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> TextObject:
        """Create a text object."""
        return TextObject(
            text,
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_field(
        self,
        binding: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 20.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> FieldObject:
        """Create a data-bound field object."""
        return FieldObject(
            binding,
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_line(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 0.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> LineObject:
        """Create a line object."""
        return LineObject(
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_rectangle(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> RectangleObject:
        """Create a rectangle object."""
        return RectangleObject(
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_image(
        self,
        source: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> ImageObject:
        """Create an image placeholder object."""
        return ImageObject(
            source,
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_barcode(
        self,
        value: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 200.0,
        height: float = 60.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        symbology: str = "code128",
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> BarcodeObject:
        """Create a barcode placeholder object."""
        return BarcodeObject(
            value,
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            symbology=symbology,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_qrcode(
        self,
        value: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 100.0,
        height: float = 100.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> QRCodeObject:
        """Create a QR code placeholder object."""
        return QRCodeObject(
            value,
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_table(
        self,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 300.0,
        height: float = 100.0,
        binding: str | None = None,
        columns: list[Mapping[str, Any]] | None = None,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> TableObject:
        """Create a table placeholder object."""
        return TableObject(
            id=id,
            x=x,
            y=y,
            width=width,
            height=height,
            binding=binding,
            columns=columns,
            position=position,
            size=size,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_custom(
        self,
        object_type: str,
        *,
        id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 0.0,
        height: float = 0.0,
        position: Position | Mapping[str, Any] | None = None,
        size: Size | Mapping[str, Any] | None = None,
        text: str = "",
        binding: Binding | Mapping[str, Any] | str | None = None,
        style: Style | Mapping[str, Any] | None = None,
        style_values: Mapping[str, Any] | None = None,
        properties: Mapping[str, Any] | None = None,
        **common: Any,
    ) -> Object:
        """Create a custom report object type."""
        return Object(
            id=id,
            type=object_type,
            x=x,
            y=y,
            width=width,
            height=height,
            position=position,
            size=size,
            text=text,
            binding=binding,
            style=_style_with_values(style, style_values),
            properties=properties,
            **common,
        )

    def create_from_dict(
        self,
        data: Mapping[str, Any],
        *,
        object_class: type[Object] | None = None,
    ) -> Object:
        """Create a report object from a JSON-compatible mapping."""
        mapping = ensure_mapping(data, context="Report object")
        properties = dict(mapping.get("properties", {}))
        position_value = mapping.get("position", properties.pop("position", None))
        size_value = mapping.get("size", properties.pop("size", None))
        position = Position.from_value(
            position_value,
            x=float(mapping.get("x", 0.0)),
            y=float(mapping.get("y", 0.0)),
        )
        size = Size.from_value(
            size_value,
            width=float(mapping.get("width", 0.0)),
            height=float(mapping.get("height", 0.0)),
        )
        style = _object_style(mapping, properties)
        binding = Binding.from_value(
            mapping.get(
                "binding",
                properties.get("binding", properties.get("field", properties.get("expression"))),
            )
        )
        text = str(mapping.get("text", properties.get("text", "")))

        for key, value in {
            "binding": binding.expression if binding else None,
            "style": style.to_dict(),
            "text": text,
        }.items():
            if value not in (None, "", {}):
                properties[key] = value

        object_type = _required_str(mapping, "type", context="Report object")
        target_class = object_class or _object_class(object_type)
        common = {
            "id": _required_str(mapping, "id", context="Report object"),
            "position": position,
            "size": size,
            "style": style,
            "band_id": _optional_str(mapping.get("band_id")),
            "layer_id": _optional_str(mapping.get("layer_id")),
            "z_index": int(mapping.get("z_index", 0)),
            "visible": bool(mapping.get("visible", True)),
            "properties": properties,
        }

        if target_class is TextObject:
            return self.create_text(text, **common)
        if target_class is FieldObject:
            expression = binding.expression if binding is not None else ""
            return self.create_field(expression, **common)
        if target_class is LineObject:
            return self.create_line(**common)
        if target_class is RectangleObject:
            return self.create_rectangle(**common)
        if target_class is ImageObject:
            source = mapping.get(
                "src",
                mapping.get("source", properties.get("src", properties.get("source", ""))),
            )
            if source not in ("", None):
                properties["src"] = str(source)
            return self.create_image(str(source or ""), **common)
        if target_class is BarcodeObject:
            return self.create_barcode(
                str(properties.get("value", "")),
                symbology=str(properties.get("symbology", "code128")),
                **common,
            )
        if target_class is QRCodeObject:
            return self.create_qrcode(str(properties.get("value", "")), **common)
        if target_class is TableObject:
            columns = properties.get("columns")
            return self.create_table(
                binding=properties.get("binding"),
                columns=columns if isinstance(columns, list) else None,
                **common,
            )
        return self.create_custom(
            object_type,
            text=text,
            binding=binding,
            **common,
        )


def _style_with_values(
    style: Style | Mapping[str, Any] | None,
    values: Mapping[str, Any] | None,
) -> Style:
    resolved = _style_value(style)
    style_values = dict(values or {})
    if not style_values:
        return resolved
    if resolved.resolved_values():
        return resolved.inherit(**style_values)
    return Style(style_values)


def _object_style(mapping: Mapping[str, Any], properties: Mapping[str, Any]) -> Style:
    style = dict(_mapping(properties.get("style")))
    style.update(_mapping(mapping.get("style")))
    for key in _STYLE_KEYS:
        if key in properties and key not in style:
            style[key] = properties[key]
    return Style.from_dict(style)


def _style_value(value: Any) -> Style:
    if value is None:
        return Style()
    if isinstance(value, Style):
        return value
    if isinstance(value, Mapping):
        return Style.from_dict(value)
    raise ReportValidationError("style must be a Style or mapping.")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _object_class(object_type: str) -> type[Object]:
    return {
        "barcode": BarcodeObject,
        "field": FieldObject,
        "image": ImageObject,
        "line": LineObject,
        "qrcode": QRCodeObject,
        "rectangle": RectangleObject,
        "table": TableObject,
        "text": TextObject,
    }.get(object_type, Object)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ReportValidationError(f"{context} requires a non-empty {key}.")
    return str(value)


_STYLE_KEYS = (
    "align",
    "background_color",
    "bold",
    "border_color",
    "border_width",
    "color",
    "fill_color",
    "font_family",
    "font_size",
    "italic",
    "line_height",
    "line_width",
    "object_fit",
    "opacity",
    "border_radius",
    "stroke_color",
    "stroke_width",
    "underline",
    "vertical_align",
)

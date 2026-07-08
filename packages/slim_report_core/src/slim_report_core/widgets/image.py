"""Image widget implementation."""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Any, ClassVar

from ..models import ReportObject
from .base import BaseWidget, html_attr, object_style, pdf_y


class ImageWidget(BaseWidget):
    """Render an image object with a safe placeholder fallback."""

    type: ClassVar[str] = "image"
    label: ClassVar[str] = "Image"

    def default_config(self) -> dict[str, Any]:
        return {
            "source": "",
            "src": "",
            "alt": "",
            "object_fit": "contain",
            "border_width": 0,
            "border_color": "#000000",
            "background_color": "transparent",
        }

    def render_html(self, obj: ReportObject, data: Any, context: Any) -> str:
        self.validate(obj)
        config = self.default_config() | obj.properties | obj.style.resolved_values()
        source = str(config.get("src") or config.get("source") or "")
        style = object_style(
            obj,
            extra={
                "border": (
                    f"{float(config.get('border_width', 0))}pt solid "
                    f"{html_attr(config.get('border_color', '#000000'))}"
                ),
                "background": html_attr(config.get("background_color", "transparent")),
                "overflow": "hidden",
            },
        )
        if not source:
            return (
                f'<div data-slim-object="{html_attr(obj.id)}" style="{style}; '
                'display: grid; place-items: center;"></div>'
            )
        return (
            f'<div data-slim-object="{html_attr(obj.id)}" style="{style}">'
            f'<img src="{html_attr(source)}" alt="{html_attr(config.get("alt", ""))}" '
            f'style="width: 100%; height: 100%; object-fit: '
            f'{html_attr(config.get("object_fit", "contain"))}; display: block;"></div>'
        )

    def render_pdf(self, canvas: Any, obj: ReportObject, data: Any, context: Any) -> None:
        self.validate(obj)
        config = self.default_config() | obj.properties | obj.style.resolved_values()
        source = str(config.get("src") or config.get("source") or "")
        reader = _image_reader(source)
        if reader is None:
            return
        canvas.drawImage(
            reader,
            obj.x,
            pdf_y(obj, context),
            width=obj.width,
            height=obj.height,
            preserveAspectRatio=str(config.get("object_fit", "contain")) == "contain",
            mask="auto",
        )


def _image_reader(source: str) -> Any | None:
    if not source or source.startswith(("http://", "https://")):
        return None
    try:
        from reportlab.lib.utils import ImageReader
    except ImportError:
        return None
    if source.startswith("data:image/"):
        try:
            _, encoded = source.split(",", 1)
            return ImageReader(BytesIO(base64.b64decode(encoded)))
        except Exception:
            return None
    try:
        return ImageReader(source)
    except Exception:
        return None

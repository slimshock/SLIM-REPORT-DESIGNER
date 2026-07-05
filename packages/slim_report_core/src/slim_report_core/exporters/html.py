"""HTML report exporter."""

from __future__ import annotations

from html import escape
from typing import Any

from .base import BaseExporter, object_to_points, render_context


class HTMLExporter(BaseExporter):
    """Export reports to absolute-positioned HTML."""

    def export(self, report: Any, data: Any = None, context: Any = None) -> str:
        template = self.normalize_template(report)
        layout = self.resolve_page_layout(template)
        renderer_context = render_context(context, layout)

        objects = sorted(template.objects, key=lambda item: item.z_index)
        rendered_objects = []
        for obj in objects:
            point_obj = object_to_points(obj, template.page.unit)
            widget = self.get_widget(point_obj)
            rendered_objects.append(widget.render_html(point_obj, data or {}, renderer_context))

        title = escape(template.metadata.title)
        page_style = (
            "position: relative; "
            f"width: {layout.width}pt; "
            f"height: {layout.height}pt; "
            "box-sizing: border-box; "
            "background: #ffffff; "
            "overflow: hidden;"
        )
        body = "\n    ".join(rendered_objects)
        return (
            "<!doctype html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            f"  <title>{title}</title>\n"
            "</head>\n"
            "<body>\n"
            f'  <div class="slim-report-page" style="{page_style}">\n'
            f"    {body}\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )


"""HTML assembly for bounded runtime-rendered pages."""

from __future__ import annotations

from html import escape

from ..rendering.context import RenderContext


def render_runtime_document(
    context: RenderContext,
    pages: list[str],
    *,
    empty_message: str | None = None,
) -> str:
    """Wrap already escaped page fragments in the existing preview page contract."""
    page = context.page
    background = "#fff" if page.transparent else escape(page.background_color, quote=True)
    notice = (
        f'<div class="slim-report-runtime-message" role="status">{escape(empty_message)}</div>'
        if empty_message
        else ""
    )
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escape(context.title)}</title>\n"
        "<style>\n"
        f"@page {{ size: {page.width_px}px {page.height_px}px; margin: 0; }}\n"
        "html,body{width:100%;min-height:100%;}"
        "body{margin:0;background:#e5e7eb;font-family:Arial,sans-serif;}"
        ".slim-report-preview{padding:24px;display:grid;gap:24px;}"
        ".slim-report-page{position:relative;margin:0 auto;background:#fff;"
        "box-shadow:0 2px 12px rgba(15,23,42,.18);overflow:hidden;"
        "break-after:page;page-break-after:always;-webkit-print-color-adjust:exact;"
        "print-color-adjust:exact;}"
        ".slim-report-page:last-child{break-after:auto;page-break-after:auto;}"
        ".slim-report-page-number{position:absolute;right:12px;bottom:8px;"
        "font:10px Arial,sans-serif;color:#94a3b8;}"
        ".slim-report-object{position:absolute;box-sizing:border-box;}"
        ".slim-report-runtime-message{position:sticky;top:0;z-index:20;padding:10px 16px;"
        "background:#fff;border-bottom:1px solid #d1d5db;color:#334155;font-size:13px;}"
        "@media print{html,body{margin:0;background:#fff;}"
        ".slim-report-runtime-message{display:none!important;}"
        ".slim-report-preview{padding:0;gap:0;}"
        ".slim-report-page{margin:0;box-shadow:none;break-after:page;page-break-after:always;}"
        ".slim-report-page:last-child{break-after:auto;page-break-after:auto;}"
        "*{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}\n"
        "</style>\n</head>\n<body>\n"
        f"{notice}<div class=\"slim-report-preview\" data-runtime-preview=\"true\">\n"
        f"{''.join(pages)}"
        "</div>\n</body>\n</html>\n"
    ).replace("background:#fff;box-shadow", f"background:{background};box-shadow")


def runtime_page_html(
    context: RenderContext,
    page_number: int,
    bands_html: str,
    objects_html: str,
) -> str:
    page = context.page
    background = "#fff" if page.transparent else escape(page.background_color, quote=True)
    return (
        f'<div class="slim-report-page" data-slim-page="{page_number}" '
        f'style="width:{page.width_px}px;height:{page.height_px}px;background:{background};">'
        f"{bands_html}{objects_html}"
        f'<div class="slim-report-page-number">Page {page_number}</div></div>\n'
    )

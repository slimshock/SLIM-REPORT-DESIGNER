"""HTML designer page helpers for the Flask adapter."""

from __future__ import annotations

import json
from html import escape
from typing import Any


def template_for_designer(template: dict[str, Any]) -> dict[str, Any]:
    """Return template JSON for the designer, with starter objects when empty."""
    editable = json.loads(json.dumps(template))
    if not editable.get("objects"):
        editable["objects"] = sample_objects()
    return editable


def render_designer_page(
    *,
    template_id: str,
    template: dict[str, Any],
    save_url: str,
    preview_url: str,
    pdf_url: str,
) -> str:
    """Render the built-in JSON designer page."""
    template_json = json.dumps(template, indent=2)
    title = escape(str(template.get("metadata", {}).get("title", template_id)))
    escaped_template_id = escape(template_id, quote=True)
    escaped_json = escape(template_json)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Slim Report Designer - {title}</title>
  <style>
    body {{
      margin: 0;
      background: #f3f4f6;
      color: #111827;
      font-family: Arial, sans-serif;
    }}
    .designer-shell {{
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
    }}
    .designer-toolbar {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: #ffffff;
      border-bottom: 1px solid #d1d5db;
    }}
    .designer-title {{
      margin-right: auto;
      font-weight: 700;
    }}
    button, a.button {{
      border: 1px solid #9ca3af;
      border-radius: 6px;
      background: #ffffff;
      color: #111827;
      cursor: pointer;
      font: inherit;
      padding: 7px 12px;
      text-decoration: none;
    }}
    button.primary {{
      background: #111827;
      border-color: #111827;
      color: #ffffff;
    }}
    .designer-body {{
      display: grid;
      grid-template-columns: minmax(320px, 1fr) minmax(360px, 1fr);
      gap: 16px;
      padding: 16px;
    }}
    textarea {{
      width: 100%;
      min-height: calc(100vh - 118px);
      box-sizing: border-box;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font: 13px Consolas, monospace;
      line-height: 1.45;
      padding: 12px;
      resize: vertical;
    }}
    iframe {{
      width: 100%;
      min-height: calc(100vh - 118px);
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
    }}
    .status {{
      min-width: 140px;
      color: #4b5563;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main class="designer-shell" data-template-id="{escaped_template_id}">
    <div class="designer-toolbar">
      <div class="designer-title">Slim Report Designer: {title}</div>
      <span id="save-status" class="status"></span>
      <button id="save-button" class="primary" type="button">Save</button>
      <button id="preview-button" type="button">Preview</button>
      <button id="pdf-button" type="button">Export PDF</button>
    </div>
    <div class="designer-body">
      <textarea id="template-json" spellcheck="false">{escaped_json}</textarea>
      <iframe id="preview-frame" title="Report preview"></iframe>
    </div>
  </main>
  <script>
    const designerConfig = {{
      saveUrl: {json.dumps(save_url)},
      previewUrl: {json.dumps(preview_url)},
      pdfUrl: {json.dumps(pdf_url)}
    }};

    const elements = {{
      editor: document.querySelector("#template-json"),
      status: document.querySelector("#save-status"),
      previewFrame: document.querySelector("#preview-frame"),
      saveButton: document.querySelector("#save-button"),
      previewButton: document.querySelector("#preview-button"),
      pdfButton: document.querySelector("#pdf-button")
    }};

    function readTemplate() {{
      return JSON.parse(elements.editor.value);
    }}

    function setStatus(message) {{
      elements.status.textContent = message;
    }}

    async function saveTemplate() {{
      setStatus("Saving...");
      const response = await fetch(designerConfig.saveUrl, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(readTemplate())
      }});
      if (!response.ok) {{
        const error = await response.json().catch(() => ({{ error: "Save failed" }}));
        throw new Error(error.error || "Save failed");
      }}
      setStatus("Saved");
    }}

    async function saveThen(action) {{
      try {{
        await saveTemplate();
        action();
      }} catch (error) {{
        setStatus(error.message);
      }}
    }}

    elements.saveButton.addEventListener("click", () => {{
      saveTemplate().catch((error) => setStatus(error.message));
    }});

    elements.previewButton.addEventListener("click", () => {{
      saveThen(() => {{
        elements.previewFrame.src = designerConfig.previewUrl;
        window.open(designerConfig.previewUrl, "_blank");
      }});
    }});

    elements.pdfButton.addEventListener("click", () => {{
      saveThen(() => window.open(designerConfig.pdfUrl, "_blank"));
    }});
  </script>
</body>
</html>
"""


def sample_objects() -> list[dict[str, Any]]:
    """Return starter objects for an empty template."""
    return [
        {
            "id": "title",
            "type": "text",
            "x": 50,
            "y": 40,
            "width": 500,
            "height": 32,
            "text": "LABORATORY RESULT",
            "style": {
                "font_size": 22,
                "bold": True,
            },
        },
        {
            "id": "patient_name",
            "type": "field",
            "x": 50,
            "y": 90,
            "width": 360,
            "height": 22,
            "binding": "patient.name",
            "style": {
                "font_size": 13,
                "bold": True,
            },
        },
        {
            "id": "separator",
            "type": "line",
            "x": 50,
            "y": 130,
            "width": 500,
            "height": 0,
            "style": {
                "stroke_width": 1,
            },
        },
        {
            "id": "result_box",
            "type": "rectangle",
            "x": 50,
            "y": 150,
            "width": 500,
            "height": 118,
            "style": {
                "border_width": 1,
            },
        },
        {
            "id": "hgb_value",
            "type": "field",
            "x": 75,
            "y": 176,
            "width": 160,
            "height": 22,
            "binding": "result.HGB",
            "style": {
                "font_size": 12,
            },
        },
        {
            "id": "wbc_value",
            "type": "field",
            "x": 75,
            "y": 210,
            "width": 160,
            "height": 22,
            "binding": "result.WBC",
            "style": {
                "font_size": 12,
            },
        },
        {
            "id": "plt_value",
            "type": "field",
            "x": 75,
            "y": 244,
            "width": 160,
            "height": 22,
            "binding": "result.PLT",
            "style": {
                "font_size": 12,
            },
        },
    ]

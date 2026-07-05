import { createDefaultTemplate, normalizeTemplate } from "./objects.js";

export async function loadTemplate() {
  if (!apiBase()) {
    return loadLocalTemplate();
  }
  const templateId = currentTemplateId();
  if (!templateId) {
    return loadLocalTemplate();
  }
  const response = await fetch(`${apiBase()}/templates/${encodeURIComponent(templateId)}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Template load failed"));
  }
  return normalizeTemplate(await response.json());
}

export async function saveTemplate(template) {
  const normalized = normalizeTemplate(template);
  if (!apiBase()) {
    localStorage.setItem("slim-report-template", JSON.stringify(normalized));
    return normalized;
  }
  const templateId = currentTemplateId() || normalized.metadata?.custom?.id || "untitled";
  const response = await fetch(`${apiBase()}/templates/${encodeURIComponent(templateId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(normalized)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Template save failed"));
  }
  return normalizeTemplate(await response.json());
}

export async function previewTemplate(template) {
  if (!apiBase()) {
    openHtmlPreview(localPreviewHtml(template));
    return;
  }
  const response = await fetch(`${apiBase()}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(template)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Preview failed"));
  }
  const html = await response.text();
  openHtmlPreview(html);
}

export async function exportPdf(template) {
  if (!apiBase()) {
    throw new Error("PDF export requires a backend API.");
  }
  const response = await fetch(`${apiBase()}/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(template)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "PDF export failed"));
  }
  const blob = await response.blob();
  downloadBlob(blob, "report-template.pdf");
}

function apiBase() {
  return window.SLIM_REPORT_API_BASE || "";
}

function currentTemplateId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("template") || window.SLIM_REPORT_TEMPLATE_ID || "";
}

function loadLocalTemplate() {
  const saved = localStorage.getItem("slim-report-template");
  if (saved) {
    return normalizeTemplate(JSON.parse(saved));
  }
  return createDefaultTemplate();
}

function openHtmlPreview(html) {
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

function localPreviewHtml(template) {
  const page = template.page || {};
  const objects = (template.objects || []).map(localObjectHtml).join("\n");
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>${escapeHtml(template.metadata?.title || "Preview")}</title></head>
<body style="margin:0;background:#e5e7eb;padding:24px;font-family:Arial,sans-serif">
<div style="position:relative;margin:0 auto;background:#fff;width:${page.width || 595}px;height:${page.height || 842}px">
${objects}
</div>
</body></html>`;
}

function localObjectHtml(object) {
  const style = object.style || object.properties?.style || {};
  const value = object.type === "field"
    ? `{{ ${object.binding || object.properties?.binding || ""} }}`
    : object.text || object.properties?.text || "";
  const textDecoration = style.underline ? "underline" : "none";
  const display = object.type === "text" || object.type === "field" ? "flex" : "block";
  const box = `position:absolute;box-sizing:border-box;left:${object.x}px;top:${object.y}px;width:${object.width}px;height:${Math.max(object.height, 8)}px;display:${display};justify-content:${horizontalFlexAlign(style.align)};align-items:${verticalFlexAlign(style.vertical_align)};font-family:${style.font_family || "Arial"};font-size:${style.font_size || 12}px;font-weight:${style.bold ? 700 : 400};font-style:${style.italic ? "italic" : "normal"};text-decoration:${textDecoration};color:${style.color || "#111827"};background:${style.background_color || "transparent"};text-align:${style.align || "left"};overflow:hidden`;
  if (object.type === "line") {
    return `<div style="${box};border-top:${style.stroke_width || 1}px solid ${style.stroke_color || style.color || "#111827"}"></div>`;
  }
  if (object.type === "rectangle") {
    return `<div style="${box};border:${style.border_width || 1}px solid ${style.border_color || "#111827"};background:${style.background_color || style.fill_color || "transparent"}"></div>`;
  }
  return `<div style="${box}">${escapeHtml(value)}</div>`;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function errorMessage(response, fallback) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json().catch(() => ({}));
    return payload.error || fallback;
  }
  return (await response.text().catch(() => "")) || fallback;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  })[char]);
}

function horizontalFlexAlign(value) {
  if (value === "center") {
    return "center";
  }
  if (value === "right") {
    return "flex-end";
  }
  return "flex-start";
}

function verticalFlexAlign(value) {
  if (value === "middle") {
    return "center";
  }
  if (value === "bottom") {
    return "flex-end";
  }
  return "flex-start";
}

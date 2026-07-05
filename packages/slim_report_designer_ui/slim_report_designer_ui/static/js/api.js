import { createDefaultTemplate, normalizeTemplate, objectStyle } from "./objects.js";
import { getFieldValue } from "./data_fields.js";

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
  const bands = (template.bands || []).map((band) => localBandHtml(band, page.unit)).join("\n");
  const objects = (template.objects || []).map((object) => localObjectHtml(object, page.unit, template.data?.sample || {})).join("\n");
  const background = page.transparent ? "#fff" : page.background_color || "#fff";
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>${escapeHtml(template.metadata?.title || "Preview")}</title></head>
<body style="margin:0;background:#e5e7eb;padding:24px;font-family:Arial,sans-serif">
<div style="position:relative;margin:0 auto;background:${escapeHtml(background)};width:${unitToPx(page.width || 595, page.unit)}px;height:${unitToPx(page.height || 842, page.unit)}px">
${bands}
${objects}
</div>
</body></html>`;
}

function localBandHtml(band, unit = "px") {
  if (band.visible === false || isTransparent(band.background_color)) {
    return "";
  }
  return `<div style="position:absolute;box-sizing:border-box;left:0;top:${unitToPx(band.y, unit)}px;width:100%;height:${unitToPx(band.height, unit)}px;background:${escapeHtml(band.background_color)}"></div>`;
}

function localObjectHtml(object, unit = "px", sampleData = {}) {
  const style = objectStyle(object);
  const fieldValue = object.type === "field"
    ? getFieldValue(sampleData, object.binding || object.properties?.binding || "")
    : undefined;
  const value = object.type === "field"
    ? fieldValue === undefined || fieldValue === null ? `{{ ${object.binding || object.properties?.binding || ""} }}` : String(fieldValue)
    : object.text || object.properties?.text || "";
  const textDecoration = style.underline ? "underline" : "none";
  const display = object.type === "text" || object.type === "field" ? "flex" : "block";
  const box = `position:absolute;box-sizing:border-box;left:${unitToPx(object.x, unit)}px;top:${unitToPx(object.y, unit)}px;width:${unitToPx(object.width, unit)}px;height:${unitToPx(Math.max(object.height, 8), unit)}px;display:${display};justify-content:${horizontalFlexAlign(style.align)};align-items:${verticalFlexAlign(style.vertical_align)};font-family:${style.font_family || "Arial"};font-size:${style.font_size || 12}px;line-height:${style.line_height || 1.2};font-weight:${style.bold ? 700 : 400};font-style:${style.italic ? "italic" : "normal"};text-decoration:${textDecoration};color:${style.color || "#111827"};background:${style.background_color || "transparent"};text-align:${style.align || "left"};overflow:hidden`;
  if (object.type === "line") {
    return `<div style="${box};border-top:${style.stroke_width || 1}px solid ${style.stroke_color || style.color || "#111827"}"></div>`;
  }
  if (object.type === "rectangle") {
    return `<div style="${box};border:${style.border_width || 1}px solid ${style.border_color || "#111827"};border-radius:${style.border_radius || 0}px;background:${style.background_color || style.fill_color || "transparent"}"></div>`;
  }
  if (object.type === "image") {
    const src = object.src || object.properties?.src || object.properties?.source || "";
    const imageBox = `${box};display:grid;place-items:center;border:${style.border_width || 0}px solid ${style.border_color || "#000000"};border-radius:${style.border_radius || 0}px;opacity:${style.opacity ?? 1}`;
    if (!src) {
      return `<div style="${imageBox};color:#64748b;background:#f8fafc">Image</div>`;
    }
    return `<div style="${imageBox}"><img src="${escapeHtml(src)}" alt="${escapeHtml(object.alt || object.properties?.alt || "")}" style="width:100%;height:100%;object-fit:${style.object_fit || "contain"};display:block"></div>`;
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

function unitToPx(value, unit = "px") {
  const number = Number(value) || 0;
  if (unit === "in") {
    return number * 96;
  }
  if (unit === "mm") {
    return number * 96 / 25.4;
  }
  return number;
}

function isTransparent(value) {
  return ["", "none", "transparent"].includes(String(value || "").trim().toLowerCase());
}

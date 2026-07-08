import { createDefaultTemplate, normalizeTemplate, objectStyle } from "./objects.js";
import { ensureTemplateData, getArrayByPath, getFieldValue, getRowValue, resolveBinding } from "./data_fields.js";
import { qrSvgMarkup } from "./qrcode.js";

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
  const payload = await response.json().catch(() => ({}));
  const saved = templateFromSaveResponse(payload);
  if (!saved) {
    return normalized;
  }
  if (!hasTemplateData(saved) && hasTemplateData(normalized)) {
    ensureTemplateData(saved, normalized.data);
  }
  return normalizeTemplate(saved);
}

export async function previewTemplate(template) {
  if (!apiBase()) {
    openHtmlPreview(localPreviewHtml(template));
    return;
  }
  const response = await fetch(`${apiBase()}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(templateRequestPayload(template))
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
    body: JSON.stringify(templateRequestPayload(template))
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

function templateRequestPayload(template) {
  const normalized = normalizeTemplate(template);
  const payload = {
    template_id: currentTemplateId() || normalized.metadata?.custom?.id || "",
    template: normalized
  };
  if (normalized.data?.sample && typeof normalized.data.sample === "object") {
    payload.data = normalized.data.sample;
  }
  return payload;
}

function templateFromSaveResponse(payload) {
  if (isFullTemplate(payload)) {
    return payload;
  }
  if (isFullTemplate(payload?.template)) {
    return payload.template;
  }
  return null;
}

function isFullTemplate(value) {
  return Boolean(
    value
      && typeof value === "object"
      && value.metadata
      && value.page
      && Array.isArray(value.objects)
      && Array.isArray(value.bands)
  );
}

function hasTemplateData(template) {
  return Boolean(template?.data?.sample || (Array.isArray(template?.data?.fields) && template.data.fields.length > 0));
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
  const objects = localObjectsHtml(template, page.unit);
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

function localObjectsHtml(template, unit = "px") {
  const sampleData = template.data?.sample || {};
  const repeat = (template.bands || []).find((band) => band.id === "detail")?.repeat;
  if (!repeat?.enabled || !repeat.data_path) {
    return (template.objects || []).map((object) => localObjectHtml(object, unit, sampleData)).join("\n");
  }
  const groupHeader = (template.bands || []).find((band) => band.type === "group_header");
  if (groupHeader?.group?.field) {
    return localGroupedObjectsHtml(template, unit, sampleData, repeat, groupHeader);
  }
  const rows = getArrayByPath(sampleData, repeat.data_path);
  const rowHeight = Number(repeat.row_height) || 22;
  const detailObjects = (template.objects || []).filter((object) => objectBandId(object) === "detail");
  const outsideObjects = (template.objects || []).filter((object) => objectBandId(object) !== "detail");
  const rendered = outsideObjects.map((object) => localObjectHtml(object, unit, sampleData));
  if (rows.length === 0) {
    rendered.push(localEmptyMessageHtml(template, repeat, unit));
  }
  rows.forEach((row, rowIndex) => {
    for (const object of detailObjects) {
      rendered.push(localObjectHtml({
        ...object,
        y: (Number(object.y) || 0) + (rowIndex * rowHeight)
      }, unit, sampleData, row, repeat.data_path));
    }
  });
  return rendered.join("\n");
}

function localGroupedObjectsHtml(template, unit, sampleData, repeat, groupHeader) {
  const rows = getArrayByPath(sampleData, repeat.data_path);
  const detail = (template.bands || []).find((band) => band.id === "detail") || {};
  const groupFooter = (template.bands || []).find((band) => band.type === "group_footer");
  const rowHeight = Number(repeat.row_height) || 22;
  const headerHeight = Number(groupHeader.height) || 0;
  const footerHeight = groupFooter?.visible === false ? 0 : Number(groupFooter?.height) || 0;
  let cursor = Number(groupHeader.y ?? detail.y ?? 0) || 0;
  const rendered = (template.objects || [])
    .filter((object) => !["detail", groupHeader.id, groupFooter?.id].includes(objectBandId(object)))
    .map((object) => localObjectHtml(object, unit, sampleData));
  if (rows.length === 0) {
    rendered.push(localEmptyMessageHtml(template, repeat, unit));
    return rendered.join("\n");
  }
  const groups = sortLocalGroups(groupLocalRows(rows, groupHeader.group.field, repeat.data_path), groupHeader.group.sort);
  const groupHeaderObjects = (template.objects || []).filter((object) => objectBandId(object) === groupHeader.id);
  const detailObjects = (template.objects || []).filter((object) => objectBandId(object) === "detail");
  const groupFooterObjects = groupFooter
    ? (template.objects || []).filter((object) => objectBandId(object) === groupFooter.id)
    : [];
  for (const group of groups) {
    for (const object of groupHeaderObjects) {
      rendered.push(localObjectHtml(flowObject(object, cursor, groupHeader.y), unit, sampleData, null, repeat.data_path, group));
    }
    cursor += headerHeight;
    for (const row of group.rows) {
      for (const object of detailObjects) {
        rendered.push(localObjectHtml(flowObject(object, cursor, detail.y), unit, sampleData, row, repeat.data_path, group));
      }
      cursor += rowHeight;
    }
    if (groupFooter && groupFooter.visible !== false) {
      for (const object of groupFooterObjects) {
        rendered.push(localObjectHtml(flowObject(object, cursor, groupFooter.y), unit, sampleData, null, repeat.data_path, group));
      }
      cursor += footerHeight;
    }
  }
  return rendered.join("\n");
}

function localObjectHtml(object, unit = "px", sampleData = {}, rowData = null, repeatDataPath = "", groupData = null) {
  const style = objectStyle(object);
  const binding = object.binding || object.properties?.binding || "";
  const fieldValue = object.type === "field"
    ? resolveBinding(binding, sampleData, {
      rowData,
      repeatDataPath,
      groupData,
      pageNumber: 1,
      totalPages: 1
    })
    : undefined;
  const value = object.type === "field"
    ? fieldValue === undefined || fieldValue === null ? `{{ ${object.binding || object.properties?.binding || ""} }}` : String(fieldValue)
    : object.type === "text"
    ? resolveTextValue(object.text || object.properties?.text || "", sampleData, rowData, repeatDataPath, groupData)
    : "";
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
  if (object.type === "barcode") {
    const barcodeValue = boundObjectValue(object, sampleData, rowData, repeatDataPath, groupData) || "Barcode";
    const foreground = style.foreground_color || "#111827";
    const background = style.background_color || "#ffffff";
    const bars = `height:100%;background:repeating-linear-gradient(90deg,${foreground} 0 2px,transparent 2px 4px,${foreground} 4px 5px,transparent 5px 9px)`;
    const label = object.show_text ?? object.properties?.show_text ?? true
      ? `<div style="font:${style.font_size || 8}px Arial,sans-serif;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(barcodeValue)}</div>`
      : "";
    return `<div style="${box};display:grid;grid-template-rows:minmax(0,1fr) auto;padding:2px;color:${foreground};background:${background}"><div style="${bars}"></div>${label}</div>`;
  }
  if (object.type === "qrcode") {
    const qrValue = boundObjectValue(object, sampleData, rowData, repeatDataPath, groupData) || "QR Code";
    const foreground = style.foreground_color || "#111827";
    const background = style.background_color || "#ffffff";
    const qrSize = Math.min(Number(object.width) || 0, Number(object.height) || 0);
    const qrX = Math.max(((Number(object.width) || 0) - qrSize) / 2, 0);
    const qrY = Math.max(((Number(object.height) || 0) - qrSize) / 2, 0);
    const grid = `position:absolute;left:${qrX}px;top:${qrY}px;width:${qrSize}px;height:${qrSize}px;box-sizing:border-box`;
    return `<div title="${escapeHtml(qrValue)}" style="${box};background:${background};color:${foreground};overflow:hidden"><div style="${grid}">${qrSvgMarkup(qrValue, { foreground, background })}</div></div>`;
  }
  return `<div style="${box}">${escapeHtml(value)}</div>`;
}

function boundObjectValue(object, sampleData = {}, rowData = null, repeatDataPath = "", groupData = null) {
  const binding = object.binding || object.properties?.binding || "";
  if (binding) {
    const value = resolveBinding(binding, sampleData, {
      rowData,
      repeatDataPath,
      groupData,
      pageNumber: 1,
      totalPages: 1
    });
    if (value !== undefined && value !== null && value !== "") {
      return String(value);
    }
  }
  return String(object.value ?? object.properties?.value ?? "");
}

function resolveTextValue(text, sampleData = {}, rowData = null, repeatDataPath = "", groupData = null) {
  return String(text || "").replace(/\{\{\s*(.*?)\s*\}\}/g, (_match, binding) => {
    const value = resolveBinding(binding, sampleData, {
      rowData,
      repeatDataPath,
      groupData,
      pageNumber: 1,
      totalPages: 1
    });
    return value === undefined || value === null ? "" : String(value);
  });
}

function groupLocalRows(rows, field, dataPath) {
  const groups = [];
  const byKey = new Map();
  for (const row of rows) {
    const key = String(getRowValue(row || {}, field, dataPath) ?? "");
    if (!byKey.has(key)) {
      const group = { key, field, rows: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    byKey.get(key).rows.push(row);
  }
  return groups;
}

function sortLocalGroups(groups, sort = "none") {
  if (sort === "asc") {
    return groups.slice().sort((left, right) => left.key.localeCompare(right.key));
  }
  if (sort === "desc") {
    return groups.slice().sort((left, right) => right.key.localeCompare(left.key));
  }
  return groups;
}

function flowObject(object, cursor, bandY) {
  return {
    ...object,
    y: cursor + ((Number(object.y) || 0) - (Number(bandY) || 0))
  };
}

function repeatedFieldValue(rowData, binding, repeatDataPath, sampleData) {
  return resolveBinding(binding, sampleData, { rowData, repeatDataPath });
}

function localEmptyMessageHtml(template, repeat, unit = "px") {
  const detail = (template.bands || []).find((band) => band.id === "detail") || {};
  const top = unitToPx((Number(detail.y) || 0) + 8, unit);
  return `<div style="position:absolute;left:12px;top:${top}px;color:#64748b;font:700 12px Arial,sans-serif">${escapeHtml(repeat.empty_message || "No records")}</div>`;
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

function objectBandId(object) {
  return object?.band || object?.band_id || object?.properties?.band || "detail";
}

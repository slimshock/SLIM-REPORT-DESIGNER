import { createDefaultTemplate, normalizeTemplate, objectStyle, safePdfFilename } from "./objects.js";
import { conditionalStyleResult, ensureTemplateData, evaluateFormula, getArrayByPath, getFieldValue, getRowValue, resolveBinding } from "./data_fields.js";
import { qrSvgMarkup } from "./qrcode.js";
import { currentReportSessionKey, safeTemplateSnapshot } from "./persistence.js";

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
  const payload = await response.json();
  return normalizeTemplate(payload.template || payload);
}

export async function saveTemplate(template) {
  const normalized = normalizeTemplate(safeTemplateSnapshot(template));
  if (!apiBase()) {
    localStorage.setItem("slim-report-template", JSON.stringify(normalized));
    return normalized;
  }
  if (runtimeConfig().canSave === false) {
    throw new Error("Template saving is disabled.");
  }
  const templateId = currentTemplateId() || normalized.metadata?.custom?.id || "untitled";
  const response = await fetch(`${apiBase()}/templates/${encodeURIComponent(templateId)}`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({ template: normalized, ...normalized })
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

export async function listDataSources(template) {
  return dataSourceRequest("/designer/data-sources/list", "POST", template, {});
}

export async function createMysqlDataSource(template, values) {
  return dataSourceRequest("/designer/data-sources/mysql", "POST", template, values);
}

export async function updateMysqlDataSource(template, dataSourceId, values) {
  return dataSourceRequest(
    `/designer/data-sources/${encodeURIComponent(dataSourceId)}`,
    "PUT",
    template,
    values
  );
}

export async function deleteMysqlDataSource(template, dataSourceId) {
  return dataSourceRequest(
    `/designer/data-sources/${encodeURIComponent(dataSourceId)}`,
    "DELETE",
    template,
    {}
  );
}

export async function testMysqlDataSource(values) {
  if (!apiBase()) {
    throw new Error("Data source management requires a backend API.");
  }
  return jsonRequest(`${apiBase()}/designer/data-sources/test`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({
      template_id: currentTemplateId(),
      ...values
    })
  });
}

export async function testSavedMysqlDataSource(template, dataSourceId, runtimePassword = null) {
  const values = runtimePassword === null ? {} : { runtimePassword };
  return dataSourceRequest(
    `/designer/data-sources/${encodeURIComponent(dataSourceId)}/test`,
    "POST",
    template,
    values
  );
}

export async function listDatasets(template) {
  return dataSourceRequest("/designer/datasets/list", "POST", template, {});
}

export async function getDataset(template, datasetId) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/get`,
    "POST",
    template,
    {}
  );
}

export async function listReportingViews(template, dataSourceId) {
  return dataSourceRequest(
    `/designer/data-sources/${encodeURIComponent(dataSourceId)}/views/list`,
    "POST",
    template,
    {}
  );
}

export async function inspectReportingView(template, dataSourceId, viewName) {
  return dataSourceRequest(
    `/designer/data-sources/${encodeURIComponent(dataSourceId)}/views/inspect`,
    "POST",
    template,
    { viewName }
  );
}

export async function validateDatasetQuery(template, values) {
  return dataSourceRequest("/designer/query/validate", "POST", template, values);
}

export async function discoverDatasetQuery(template, values) {
  return dataSourceRequest("/designer/query/discover", "POST", template, values);
}

export async function createViewDataset(template, values) {
  return dataSourceRequest("/designer/datasets/view", "POST", template, values);
}

export async function createQueryDataset(template, values) {
  return dataSourceRequest("/designer/datasets/query", "POST", template, values);
}

export async function buildNewReport(configuration) {
  if (!apiBase()) {
    throw new Error("The New Report Wizard requires a backend API for final validation.");
  }
  return jsonRequest(`${apiBase()}/designer/new-report/build`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({
      template_id: currentTemplateId(),
      configuration
    })
  });
}

export async function getRuntimeParameterSchema(template, datasetId) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/runtime-parameters`,
    "POST",
    template,
    {}
  );
}

export async function validateRuntimeParameters(template, datasetId, values) {
  if (!apiBase()) {
    throw new Error("Runtime parameter validation requires a backend API.");
  }
  const response = await fetch(
    `${apiBase()}/designer/datasets/${encodeURIComponent(datasetId)}/runtime-parameters/validate`,
    {
      method: "POST",
      headers: requestHeaders(),
      body: JSON.stringify({
        ...templateRequestPayload(template),
        values
      })
    }
  );
  const payload = await response.json().catch(() => ({}));
  if (!response.ok && payload.valid === false && Array.isArray(payload.errors)) {
    return payload;
  }
  if (!response.ok) {
    throw new Error(payload?.error_detail?.message || payload?.error || "Parameter validation failed.");
  }
  return payload;
}

export async function updateViewDataset(template, datasetId, values) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/view`,
    "PUT",
    template,
    values
  );
}

export async function updateQueryDataset(template, datasetId, values) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/query`,
    "PUT",
    template,
    values
  );
}

export async function refreshViewDatasetFields(template, datasetId) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/refresh-view-fields`,
    "POST",
    template,
    {}
  );
}

export async function checkDatasetFreshness(template, datasetId, parameterValues = {}) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/freshness`,
    "POST",
    template,
    { parameterValues }
  );
}

export async function discoverExistingDatasetFields(template, datasetId, parameterValues) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/discover-fields`,
    "POST",
    template,
    { parameterValues }
  );
}

export async function applyExistingDatasetFields(template, datasetId, parameterValues) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}/apply-fields`,
    "POST",
    template,
    { parameterValues }
  );
}

export async function deleteDataset(template, datasetId) {
  return dataSourceRequest(
    `/designer/datasets/${encodeURIComponent(datasetId)}`,
    "DELETE",
    template,
    {}
  );
}

export async function previewTemplate(template) {
  if (!apiBase()) {
    openHtmlPreview(localPreviewHtml(template));
    return;
  }
  const response = await fetch(`${apiBase()}/preview`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(templateRequestPayload(template))
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Preview failed"));
  }
  const html = await response.text();
  openHtmlPreview(html);
}

export async function startLivePreview(template, request) {
  if (!apiBase()) {
    throw new Error("Live data preview requires a backend API.");
  }
  const response = await fetch(`${apiBase()}/designer/preview/live`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({
      ...templateRequestPayload(template),
      requestId: request.requestId,
      datasetId: request.datasetId,
      parameterValues: request.parameterValues || {},
      options: request.options || {}
    })
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      payload?.error?.message || payload?.error_detail?.message || "Live preview failed."
    );
    error.code = payload?.error?.code || payload?.error_detail?.code || "preview_failed";
    throw error;
  }
  return payload;
}

export async function inspectReopenedTemplate(template) {
  if (!apiBase()) {
    return { valid: true, canEdit: true, canPreview: true, issues: [] };
  }
  return dataSourceRequest("/designer/reopen/inspect", "POST", template, {});
}

export async function inspectPreviewReadiness(template, datasetId = null) {
  if (!apiBase()) {
    return { ready: true, datasetId, issues: [] };
  }
  return dataSourceRequest("/designer/preview/readiness", "POST", template, { datasetId });
}

export async function validateTemplateSave(template) {
  if (!apiBase()) {
    return { canSave: true, structurallyValid: true, runtimeReady: true, warnings: [] };
  }
  return dataSourceRequest("/designer/save/validate", "POST", template, {});
}

export async function clearRuntimeCredentials(dataSourceId = null) {
  if (!apiBase()) {
    return { ok: true };
  }
  return jsonRequest(`${apiBase()}/designer/credentials/clear`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify({
      template_id: currentTemplateId(),
      reportSessionKey: currentReportSessionKey(),
      dataSourceId
    })
  });
}

export async function cancelLivePreview(requestId) {
  if (!apiBase()) {
    return { success: false, cancelled: false };
  }
  const response = await fetch(
    `${apiBase()}/designer/preview/${encodeURIComponent(requestId)}/cancel`,
    {
      method: "POST",
      headers: requestHeaders(),
      body: JSON.stringify({ template_id: currentTemplateId() })
    }
  );
  return response.json().catch(() => ({ success: false, cancelled: false }));
}

export async function printPreview(template) {
  if (!apiBase()) {
    openHtmlPreview(localPreviewHtml(template));
    return;
  }
  const templateId = currentTemplateId() || template.metadata?.custom?.id || "";
  if (!templateId) {
    throw new Error("Print preview requires a saved template id.");
  }
  const root = apiBase().replace(/\/api\/?$/, "");
  const params = new URLSearchParams(currentQueryParams());
  const query = params.toString();
  window.open(
    `${root}/print/${encodeURIComponent(templateId)}${query ? `?${query}` : ""}`,
    "_blank",
    "noopener"
  );
}

export async function exportPdf(template) {
  if (!apiBase()) {
    throw new Error("PDF export requires a backend API.");
  }
  const response = await fetch(`${apiBase()}/export/pdf`, {
    method: "POST",
    headers: requestHeaders(),
    body: JSON.stringify(templateRequestPayload(template))
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "PDF export failed"));
  }
  const blob = await response.blob();
  downloadBlob(blob, filenameFromContentDisposition(response) || defaultPdfFilename(template));
}

function apiBase() {
  return runtimeConfig().apiBase || window.SLIM_REPORT_API_BASE || "";
}

function currentTemplateId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("template") || runtimeConfig().templateId || window.SLIM_REPORT_TEMPLATE_ID || "";
}

function runtimeConfig() {
  const legacyConfig = window.SLIM_REPORT_CONFIG || {};

  return {
    apiBase: legacyConfig.apiBase || metaContent("slim-report-api-base"),
    templateId: legacyConfig.templateId || metaContent("slim-report-template-id"),
    canSave:
      typeof legacyConfig.canSave === "boolean"
        ? legacyConfig.canSave
        : metaBoolean("slim-report-can-save"),
    saveEnabled:
      typeof legacyConfig.saveEnabled === "boolean"
        ? legacyConfig.saveEnabled
        : metaBoolean("slim-report-save-enabled"),
    csrfHeaderName:
      legacyConfig.csrfHeaderName || metaContent("slim-report-csrf-header"),
    csrfToken:
      legacyConfig.csrfToken || metaContent("slim-report-csrf-token")
  };
}

function metaContent(name) {
  return document.querySelector(`meta[name="${name}"]`)?.content || "";
}

function metaBoolean(name) {
  const value = metaContent(name);
  if (!value) {
    return undefined;
  }
  return value.toLowerCase() === "true";
}

function requestHeaders() {
  const headers = { "Content-Type": "application/json" };
  const config = runtimeConfig();
  if (config.csrfHeaderName && config.csrfToken) {
    headers[config.csrfHeaderName] = config.csrfToken;
  }
  return headers;
}

async function dataSourceRequest(path, method, template, values) {
  if (!apiBase()) {
    throw new Error("Data source management requires a backend API.");
  }
  return jsonRequest(`${apiBase()}${path}`, {
    method,
    headers: requestHeaders(),
    body: JSON.stringify({
      ...templateRequestPayload(template),
      ...values
    })
  });
}

async function jsonRequest(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      payload?.error_detail?.message || payload?.error || "Data source request failed."
    );
    error.code = payload?.error_detail?.code || "data_source_request_failed";
    error.dependents = Array.isArray(payload?.dependents) ? payload.dependents : [];
    throw error;
  }
  return payload;
}

function templateRequestPayload(template) {
  const normalized = normalizeTemplate(safeTemplateSnapshot(template));
  const payload = {
    template_id: currentTemplateId() || normalized.metadata?.custom?.id || "",
    template: normalized,
    request_args: currentQueryParams(),
    reportSessionKey: currentReportSessionKey()
  };
  if (normalized.data?.sample && typeof normalized.data.sample === "object") {
    payload.data = normalized.data.sample;
  }
  return payload;
}

function currentQueryParams() {
  return Object.fromEntries(new URLSearchParams(window.location.search).entries());
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
  const width = unitToPx(page.width || 595, page.unit);
  const height = unitToPx(page.height || 842, page.unit);
  const toolbar = page.print?.show_browser_print_button === false
    ? ""
    : '<div class="slim-report-preview-toolbar"><button class="slim-report-print-button" type="button" onclick="window.print()">Print</button></div>';
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>${escapeHtml(template.metadata?.title || "Preview")}</title>
<style>
@page { size: ${width}px ${height}px; margin: 0; }
body { margin: 0; background: #e5e7eb; padding: 24px; font-family: Arial, sans-serif; }
.slim-report-preview-toolbar { position: sticky; top: 0; z-index: 10; margin: -24px -24px 24px; padding: 12px 24px; background: rgba(255,255,255,0.96); border-bottom: 1px solid #d1d5db; }
.slim-report-print-button { border: 1px solid #94a3b8; background: #fff; border-radius: 4px; padding: 6px 10px; font: 600 12px Arial, sans-serif; color: #111827; cursor: pointer; }
.slim-report-page { position: relative; margin: 0 auto; break-after: page; page-break-after: always; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
@media print { body { background: #fff; padding: 0; } button, .slim-report-preview-toolbar, .slim-report-print-button { display: none !important; } .slim-report-page { margin: 0; box-shadow: none; } * { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style></head>
<body>
${toolbar}
<div class="slim-report-page" style="background:${escapeHtml(background)};width:${width}px;height:${height}px">
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
  const baseStyle = objectStyle(object);
  const binding = object.binding || object.properties?.binding || "";
  const formula = object.formula ?? object.properties?.formula ?? "";
  const formulaMode = Boolean(object.formula_mode ?? object.properties?.formula_mode ?? false);
  const fieldContext = {
    rowData,
    repeatDataPath,
    groupData,
    pageNumber: 1,
    totalPages: 1
  };
  const conditional = conditionalStyleResult(object, baseStyle, sampleData, fieldContext);
  if (conditional.hidden) {
    return "";
  }
  const style = conditional.style;
  const fieldValue = object.type === "field"
    ? fieldObjectValue({ binding, formula, formulaMode }, sampleData, fieldContext)
    : undefined;
  const value = object.type === "field"
    ? fieldValue === undefined || fieldValue === null
      ? formulaMode && formula ? `{{ formula: ${formula} }}` : `{{ ${object.binding || object.properties?.binding || ""} }}`
      : String(fieldValue)
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
    const src = imageSource(object.src || object.properties?.src || object.properties?.source);
    const imageBox = `${box};display:grid;place-items:center;border:${style.border_width || 0}px solid ${style.border_color || "#000000"};border-radius:${style.border_radius || 0}px;opacity:${style.opacity ?? 1}`;
    if (!src) {
      return `<div style="${imageBox}"></div>`;
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

function imageSource(value) {
  const text = String(value || "").trim();
  if (!text || ["none", "null", "undefined"].includes(text.toLowerCase())) {
    return "";
  }
  if (text.startsWith("{{") && text.endsWith("}}")) {
    return "";
  }
  return text;
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

function fieldObjectValue(field, sampleData = {}, context = {}) {
  if (field.formulaMode && String(field.formula || "").trim()) {
    const result = evaluateFormula(field.formula, sampleData, context);
    if (!result.error) {
      return result.value;
    }
    if (!field.binding) {
      return "";
    }
  }
  return resolveBinding(field.binding, sampleData, context);
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

function filenameFromContentDisposition(response) {
  const header = response.headers?.get?.("content-disposition") || "";
  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) {
    return safePdfFilename(decodeURIComponent(utf8Match[1]));
  }
  const match = header.match(/filename="?([^";]+)"?/i);
  return match ? safePdfFilename(match[1]) : "";
}

function defaultPdfFilename(template) {
  const print = template.page?.print || {};
  return safePdfFilename(print.default_filename || template.metadata?.title || template.metadata?.name || "report");
}

async function errorMessage(response, fallback) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json().catch(() => ({}));
    if (typeof payload.error === "string") {
      return payload.error;
    }
    if (payload.error?.message) {
      return payload.error.message;
    }
    if (payload.error_detail?.message) {
      return payload.error_detail.message;
    }
    return fallback;
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

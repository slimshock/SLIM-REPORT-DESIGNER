import { clampObjectToBand, getBandForObject, objectStyle } from "./objects.js";
import { gridSizeForUnit, maybeSnap, screenDeltaToRealDelta } from "./canvas_settings.js";
import { conditionalStyleResult, evaluateFormula, getArrayByPath, getFieldValue, getRowValue, resolveBinding } from "./data_fields.js";
import { appendQrSvg } from "./qrcode.js";

export function createCanvasController({
  canvas,
  getTemplate,
  getSelectedIds,
  getPrimarySelectedId,
  getActiveBandId = () => "detail",
  getCanvasSettings,
  onSelect,
  onSelectBand = () => {},
  onChange,
  onCaptureHistory = () => null,
  onCommitHistory = () => {}
}) {
  let dragState = null;

  canvas.addEventListener("pointerdown", (event) => {
    const objectElement = event.target.closest(".report-object");

    if (!objectElement) {
      const bandElement = event.target.closest(".report-band");
      if (bandElement?.dataset.bandId) {
        onSelect(null);
        onSelectBand(bandElement.dataset.bandId);
        return;
      }
      onSelect(null);
      return;
    }

    const objectId = objectElement.dataset.objectId;
    const object = findObject(getTemplate(), objectId);

    if (!object) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const resizing = Boolean(event.target.closest(".resize-handle"));

    const toggle = event.shiftKey || event.ctrlKey || event.metaKey;
    onSelect(object.id, { toggle });
    if (toggle) {
      return;
    }

    const currentObject = findObject(getTemplate(), objectId);

    if (!currentObject) {
      return;
    }
    if (currentObject.locked || getBandForObject(getTemplate(), currentObject)?.locked) {
      return;
    }
    const selectedIds = getSelectedIds();
    const movingIds = resizing
      ? [objectId]
      : selectedIds.includes(objectId) ? selectedIds : [objectId];
    const movingObjects = movingIds
      .map((id) => findObject(getTemplate(), id))
      .filter((item) => item && !item.locked && !getBandForObject(getTemplate(), item)?.locked);
    if (movingObjects.length === 0) {
      return;
    }

    dragState = {
      objectId,
      movingObjects: movingObjects.map((item) => ({
        id: item.id,
        x: Number(item.x) || 0,
        y: Number(item.y) || 0,
        width: Number(item.width) || 0,
        height: Number(item.height) || 0
      })),
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: Number(currentObject.x) || 0,
      startY: Number(currentObject.y) || 0,
      startWidth: Number(currentObject.width) || 0,
      startHeight: Number(currentObject.height) || 0,
      startAspectRatio: Number(currentObject.width) && Number(currentObject.height)
        ? Number(currentObject.width) / Number(currentObject.height)
        : 1,
      resizing,
      captureElement: objectElement,
      changed: false,
      historySnapshot: onCaptureHistory(),
    };
    safeSetPointerCapture(objectElement, event);
  });

  document.addEventListener("pointermove", (event) => {
    if (!dragState) {
      return;
    }

    if (
      event.pointerId !== undefined &&
      dragState.pointerId !== undefined &&
      event.pointerId !== dragState.pointerId
    ) {
      return;
    }

    const object = findObject(getTemplate(), dragState.objectId);

    if (!object) {
      dragState = null;
      return;
    }

    event.preventDefault();

    const dx = event.clientX - dragState.startClientX;
    const dy = event.clientY - dragState.startClientY;
    const settings = getCanvasSettings();
    const unitScale = unitToPx(1, getTemplate().page?.unit);
    const realDx = screenDeltaToRealDelta(dx, settings.zoom) / unitScale;
    const realDy = screenDeltaToRealDelta(dy, settings.zoom) / unitScale;

    if (dragState.resizing) {
      if (object.locked || getBandForObject(getTemplate(), object)?.locked) {
        return;
      }
      object.width = Math.max(8, Math.round(dragState.startWidth + realDx));
      object.height = Math.max(
        object.type === "line" ? 0 : 8,
        Math.round(dragState.startHeight + realDy)
      );
      object.width = Math.max(8, Math.round(maybeSnap(object.width, settings, unitScale)));
      if (object.type !== "line") {
        object.height = Math.max(8, Math.round(maybeSnap(object.height, settings, unitScale)));
      }
      if (object.type === "image" && object.properties?.maintain_aspect_ratio) {
        object.height = Math.max(8, Math.round(object.width / dragState.startAspectRatio));
      }
    } else {
      const adjusted = constrainedGroupDelta(dragState.movingObjects, realDx, realDy, getTemplate());
      for (const item of dragState.movingObjects) {
        const target = findObject(getTemplate(), item.id);
        if (!target || target.locked) {
          continue;
        }
        target.x = Math.round(maybeSnap(item.x + adjusted.dx, settings, unitScale));
        target.y = Math.round(maybeSnap(item.y + adjusted.dy, settings, unitScale));
        clampObjectToBand(getTemplate(), target);
      }
    }

    if (dragState.resizing) {
      clampObjectToBand(getTemplate(), object);
    }
    dragState.changed = true;
    onChange();
  });

  document.addEventListener("pointerup", (event) => {
    if (!dragState) {
      return;
    }

    if (
      event.pointerId !== undefined &&
      dragState.pointerId !== undefined &&
      event.pointerId !== dragState.pointerId
    ) {
      return;
    }

    safeReleasePointerCapture(dragState.captureElement, event);
    if (dragState.changed) {
      onCommitHistory(dragState.historySnapshot, dragState.resizing ? "Resize object" : "Move object");
    }
    dragState = null;
  });

  document.addEventListener("pointercancel", (event) => {
    if (dragState) {
      safeReleasePointerCapture(dragState.captureElement, event);
    }
    dragState = null;
  });

  document.addEventListener("keydown", (event) => {
    if (isEditingText(event.target)) {
      return;
    }

    const selectedIds = getSelectedIds();

    if (selectedIds.length === 0) {
      return;
    }

    if (event.key === "Delete") {
      event.preventDefault();
      onSelect(null, { deleteSelected: true });
      return;
    }

    const settings = getCanvasSettings();
    const unitScale = unitToPx(1, getTemplate().page?.unit);
    const step = event.shiftKey ? gridSizeForUnit(settings, unitScale) : 1;
    const snapshot = onCaptureHistory();
    let changed = false;

    let dx = 0;
    let dy = 0;
    if (event.key === "ArrowLeft") {
      dx = -step;
    } else if (event.key === "ArrowRight") {
      dx = step;
    } else if (event.key === "ArrowUp") {
      dy = -step;
    } else if (event.key === "ArrowDown") {
      dy = step;
    }
    if (dx !== 0 || dy !== 0) {
      for (const object of selectedIds.map((id) => findObject(getTemplate(), id))) {
        if (!object || object.locked || getBandForObject(getTemplate(), object)?.locked) {
          continue;
        }
        object.x = Math.round((Number(object.x) || 0) + dx);
        object.y = Math.round((Number(object.y) || 0) + dy);
        clampObjectToBand(getTemplate(), object);
        changed = true;
      }
    }

    if (changed) {
      event.preventDefault();
      onCommitHistory(snapshot, "Move object");
      onChange();
    }
  });

  return {
    render() {
      renderCanvas(
        canvas,
        getTemplate(),
        getSelectedIds(),
        getPrimarySelectedId(),
        getCanvasSettings(),
        getActiveBandId()
      );
    },
  };
}

function safeSetPointerCapture(element, event) {
  if (!element || !event || event.pointerId === undefined || event.pointerId === null) {
    return;
  }
  if (typeof element.setPointerCapture !== "function") {
    return;
  }
  try {
    element.setPointerCapture(event.pointerId);
  } catch (err) {
    // Pointer capture is optional. Dragging must still work without it.
  }
}

function safeReleasePointerCapture(element, event) {
  if (!element || !event || event.pointerId === undefined || event.pointerId === null) {
    return;
  }
  if (typeof element.releasePointerCapture !== "function") {
    return;
  }
  try {
    element.releasePointerCapture(event.pointerId);
  } catch (err) {
    // Ignore; document-level pointerup fallback handles cleanup.
  }
}

export function renderCanvas(
  canvas,
  template,
  selectedIds = [],
  primarySelectedId = null,
  settings = {},
  activeBandId = "detail"
) {
  const page = template.page || {};
  const zoom = Number(settings.zoom) || 1;
  const width = unitToPx(page.width || 595, page.unit);
  const height = unitToPx(page.height || 842, page.unit);
  const shell = canvas.parentElement;

  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  canvas.style.backgroundColor = page.transparent ? "#ffffff" : page.background_color || "#ffffff";
  canvas.style.backgroundSize = `${settings.grid_size || 10}px ${settings.grid_size || 10}px`;
  canvas.dataset.transparent = page.transparent ? "true" : "false";
  canvas.dataset.showGrid = settings.show_grid === false ? "false" : "true";
  canvas.style.transform = `scale(${zoom})`;
  canvas.style.transformOrigin = "top left";
  if (shell) {
    shell.style.width = `${width * zoom}px`;
    shell.style.height = `${height * zoom}px`;
  }
  canvas.innerHTML = "";

  for (const band of template.bands || []) {
    canvas.appendChild(renderBand(band, page.unit, activeBandId, settings));
  }
  const repeat = activeRepeat(template);
  const repeatRows = repeat ? getArrayByPath(template.data?.sample || {}, repeat.data_path) : [];
  for (const object of template.objects || []) {
    const objectRepeat = repeat && objectBandId(object) === "detail";
    const groupData = sampleGroupForObject(template, object);
    canvas.appendChild(renderObject(object, selectedIds, primarySelectedId, page.unit, {
      sampleData: template.data?.sample || {},
      showSampleData: Boolean(settings.show_sample_data),
      rowData: objectRepeat ? repeatRows[0] : null,
      repeatDataPath: objectRepeat ? repeat.data_path : "",
      groupData
    }));
  }
  if (repeat && settings.show_sample_data && settings.show_repeated_rows) {
    renderRepeatedPreviewCopies(canvas, template, selectedIds, primarySelectedId, page.unit, repeat, repeatRows);
  }
  if (selectedIds.length > 1) {
    const selectedObjects = (template.objects || []).filter((object) => selectedIds.includes(object.id));
    const bounds = objectBounds(selectedObjects, page.unit);
    if (bounds) {
      const group = document.createElement("div");
      group.className = "selection-bounds";
      group.style.left = `${bounds.left}px`;
      group.style.top = `${bounds.top}px`;
      group.style.width = `${bounds.width}px`;
      group.style.height = `${bounds.height}px`;
      canvas.appendChild(group);
    }
  }
}

function renderBand(band, unit = "px", activeBandId = "detail", settings = {}) {
  const element = document.createElement("div");
  element.className = "report-band";
  if (band.id === activeBandId) {
    element.classList.add("active");
  }
  if (["group_header", "group_footer"].includes(band.type)) {
    element.classList.add("group-band");
  }
  if (band.visible === false) {
    element.classList.add("hidden-band");
  }
  if (band.locked) {
    element.classList.add("locked-band");
  }
  element.dataset.bandId = band.id;
  element.style.top = `${unitToPx(Number(band.y) || 0, unit)}px`;
  element.style.height = `${unitToPx(Number(band.height) || 0, unit)}px`;
  element.style.background = band.visible === false ? "transparent" : band.background_color || "transparent";

  const label = document.createElement("span");
  label.className = "report-band-label";
  label.textContent = `${band.name || band.id}${band.locked ? " · Locked" : ""}`;
  const repeatText = band.id === "detail" && band.repeat?.enabled && settings.show_repeated_rows
    ? ` - Repeating Detail: ${band.repeat.data_path || "missing data path"}`
    : "";
  const groupText = ["group_header", "group_footer"].includes(band.type)
    ? `: ${band.group?.field || "missing field"}`
    : "";
  label.textContent = `${band.name || band.id}${groupText}${band.locked ? " - Locked" : ""}${repeatText}`;
  element.appendChild(label);
  return element;
}

function renderObject(object, selectedIds = [], primarySelectedId = null, unit = "px", options = {}) {
  const element = document.createElement("div");

  element.className = "report-object";
  if (options.previewCopy) {
    element.classList.add("repeat-preview-copy");
  }

  if (!options.previewCopy && selectedIds.includes(object.id)) {
    element.classList.add("selected");
  }
  if (!options.previewCopy && object.id === primarySelectedId) {
    element.classList.add("primary-selected");
  }
  if (object.locked) {
    element.classList.add("locked");
  }

  if (!options.previewCopy) {
    element.dataset.objectId = object.id;
  }
  element.dataset.type = object.type;

  element.style.left = `${unitToPx(Number(object.x) || 0, unit)}px`;
  element.style.top = `${unitToPx(Number(object.y) || 0, unit)}px`;
  element.style.width = `${unitToPx(Number(object.width) || 0, unit)}px`;
  element.style.height = `${unitToPx(Math.max(Number(object.height) || 0, object.type === "line" ? 6 : 8), unit)}px`;

  let style = objectStyle(object);
  const conditionContext = {
    rowData: options.rowData,
    repeatDataPath: options.repeatDataPath,
    groupData: options.groupData,
    pageNumber: 1,
    totalPages: 1
  };
  const conditional = options.showSampleData
    ? conditionalStyleResult(object, style, options.sampleData, conditionContext)
    : { style, hidden: false };
  style = conditional.style;
  if (conditional.hidden) {
    element.classList.add("condition-hidden");
  }

  element.style.fontSize = `${Number(style.font_size) || 12}px`;
  element.style.fontFamily = style.font_family || "Arial";
  element.style.fontWeight = style.bold ? "700" : "400";
  element.style.fontStyle = style.italic ? "italic" : "normal";
  element.style.textDecoration = style.underline ? "underline" : "none";
  element.style.lineHeight = `${Number(style.line_height) || 1.2}`;
  element.style.color = style.color || "#111827";
  element.style.background = style.background_color || "transparent";
  element.style.textAlign = style.align || "left";
  element.style.display = object.type === "text" || object.type === "field" ? "flex" : "";
  element.style.justifyContent = horizontalFlexAlign(style.align);
  element.style.alignItems = verticalFlexAlign(style.vertical_align);

  if (object.type === "text") {
    element.textContent = object.text || object.properties?.text || "Text";
  } else if (object.type === "field") {
    const binding = object.binding || object.properties?.binding || "";
    const formula = object.formula ?? object.properties?.formula ?? "";
    const formulaMode = Boolean(object.formula_mode ?? object.properties?.formula_mode ?? false);
    const context = {
        rowData: options.rowData,
        repeatDataPath: options.repeatDataPath,
        groupData: options.groupData,
        pageNumber: 1,
        totalPages: 1
      };
    const sampleValue = options.showSampleData
      ? fieldPreviewValue({ binding, formula, formulaMode }, options.sampleData, context)
      : undefined;
    if (options.showSampleData && sampleValue !== undefined && sampleValue !== null && sampleValue !== "") {
      element.textContent = String(sampleValue);
    } else {
      element.textContent = formulaMode && formula ? `{{ formula: ${formula} }}` : `{{ ${binding} }}`;
      if (options.showSampleData && (binding || formula)) {
        element.classList.add("unresolved-field");
      }
    }
  } else if (object.type === "line") {
    const line = document.createElement("div");
    line.className = "line-preview";
    line.style.borderTopWidth = `${Number(style.stroke_width) || 1}px`;
    line.style.borderTopColor = style.stroke_color || style.color || "#111827";
    element.appendChild(line);
  } else if (object.type === "rectangle") {
    const rectangle = document.createElement("div");
    rectangle.className = "rectangle-preview";
    rectangle.style.borderWidth = `${Number(style.border_width) || 1}px`;
    rectangle.style.borderColor = style.border_color || "#111827";
    rectangle.style.borderRadius = `${Number(style.border_radius) || 0}px`;
    rectangle.style.background = style.background_color || "transparent";
    element.appendChild(rectangle);
  } else if (object.type === "image") {
    element.classList.add("image-object");
    element.style.background = style.background_color || "transparent";
    element.style.border = `${Number(style.border_width) || 0}px solid ${style.border_color || "#000000"}`;
    element.style.borderRadius = `${Number(style.border_radius) || 0}px`;
    element.style.opacity = `${Number(style.opacity ?? 1)}`;
    const src = imageSource(object.src || object.properties?.src || object.properties?.source);
    if (src) {
      const image = document.createElement("img");
      image.src = src;
      image.alt = object.alt || object.properties?.alt || "";
      image.draggable = false;
      image.style.objectFit = style.object_fit || "contain";
      element.appendChild(image);
    }
  } else if (object.type === "table") {
    element.classList.add("table-object");
    element.style.background = style.background_color || "#ffffff";
    element.style.borderRadius = `${Number(style.border_radius) || 0}px`;
    element.style.display = "block";
    element.style.color = "";
    element.style.fontSize = "";
    element.appendChild(renderTablePreview(object, options));
  } else if (object.type === "barcode") {
    element.classList.add("barcode-object");
    element.style.display = "grid";
    element.style.background = style.background_color || "#ffffff";
    element.style.color = style.foreground_color || "#111827";
    element.appendChild(renderBarcodePreview(object, options));
  } else if (object.type === "qrcode") {
    element.classList.add("qrcode-object");
    element.style.display = "grid";
    element.style.padding = "0";
    element.style.background = style.background_color || "#ffffff";
    element.style.color = style.foreground_color || "#111827";
    element.appendChild(renderQrCodePreview(object, options));
  }

  if (object.locked) {
    const lock = document.createElement("span");
    lock.className = "lock-indicator";
    lock.textContent = "Locked";
    element.appendChild(lock);
  }

  if (conditional.hidden) {
    const hidden = document.createElement("span");
    hidden.className = "condition-hidden-indicator";
    hidden.textContent = "Hidden by condition";
    element.appendChild(hidden);
  }

  if (!options.previewCopy && object.id === primarySelectedId && !object.locked) {
    const handle = document.createElement("div");
    handle.className = "resize-handle";
    element.appendChild(handle);
  }

  return element;
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

function repeatedFieldValue(rowData, binding, repeatDataPath, sampleData) {
  return resolveBinding(binding, sampleData, { rowData, repeatDataPath });
}

function fieldPreviewValue(field, sampleData = {}, context = {}) {
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

function renderTablePreview(object, options = {}) {
  const spec = tableSpec(object);
  const rows = getArrayByPath(options.sampleData || {}, spec.data_path);
  const table = document.createElement("table");
  table.className = "table-preview";
  table.style.borderColor = spec.border.color;
  table.style.borderWidth = `${spec.border.width}px`;
  table.style.background = objectStyle(object).background_color || "#ffffff";

  const colgroup = document.createElement("colgroup");
  for (const column of spec.columns) {
    const col = document.createElement("col");
    col.style.width = `${columnWidthPercent(column, spec.columns)}%`;
    colgroup.appendChild(col);
  }
  table.appendChild(colgroup);

  if (spec.header.visible) {
    const thead = document.createElement("thead");
    const tr = document.createElement("tr");
    for (const column of spec.columns) {
      const th = document.createElement("th");
      th.textContent = column.label;
      th.style.height = `${spec.header.height}px`;
      th.style.background = spec.header.background_color;
      th.style.color = spec.header.color;
      th.style.fontSize = `${spec.header.font_size}px`;
      th.style.fontWeight = spec.header.bold ? "700" : "400";
      th.style.textAlign = column.align;
      tr.appendChild(th);
    }
    thead.appendChild(tr);
    table.appendChild(thead);
  }

  const tbody = document.createElement("tbody");
  const headerHeight = spec.header.visible ? spec.header.height : 0;
  const maxRows = Math.max(1, Math.floor((Number(object.height) - headerHeight) / Math.max(spec.row.height, 1)));
  const visibleRows = options.showSampleData ? rows.slice(0, maxRows) : [];
  const bodyRows = visibleRows.length > 0
    ? visibleRows
    : Array.from({ length: Math.min(maxRows, 4) }, () => ({}));
  for (const [rowIndex, row] of bodyRows.entries()) {
    const tr = document.createElement("tr");
    const rowBackground = rowIndex % 2 === 1
      ? spec.row.alternate_background_color
      : spec.row.background_color;
    for (const column of spec.columns) {
      const td = document.createElement("td");
      td.textContent = options.showSampleData && visibleRows.length > 0
        ? tableCellValue(column, row, spec.data_path, options.sampleData)
        : `{{ ${column.binding} }}`;
      td.style.height = `${spec.row.height}px`;
      td.style.background = rowBackground;
      td.style.color = spec.row.color;
      td.style.fontSize = `${spec.row.font_size}px`;
      td.style.textAlign = column.align;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function renderBarcodePreview(object, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "barcode-preview";
  const bars = document.createElement("div");
  bars.className = "barcode-bars";
  const label = document.createElement("div");
  label.className = "barcode-label";
  label.textContent = objectPreviewValue(object, options) || "Barcode";
  wrapper.appendChild(bars);
  if (object.show_text ?? object.properties?.show_text ?? true) {
    wrapper.appendChild(label);
  }
  return wrapper;
}

function renderQrCodePreview(object, options = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = "qrcode-preview";
  const value = objectPreviewValue(object, options) || "QR Code";
  const style = objectStyle(object);
  wrapper.title = value;
  const qrSize = Math.max(Math.min(Number(object.width) || 0, Number(object.height) || 0), 0);
  const qrX = Math.max(((Number(object.width) || 0) - qrSize) / 2, 0);
  const qrY = Math.max(((Number(object.height) || 0) - qrSize) / 2, 0);
  appendQrSvg(wrapper, {
    value,
    left: qrX,
    top: qrY,
    size: qrSize,
    foreground: "currentColor",
    background: style.background_color || "#ffffff"
  });
  return wrapper;
}

function objectPreviewValue(object, options = {}) {
  const binding = object.binding || object.properties?.binding || "";
  if (options.showSampleData && binding) {
    const value = resolveBinding(binding, options.sampleData, {
      rowData: options.rowData,
      repeatDataPath: options.repeatDataPath,
      groupData: options.groupData,
      pageNumber: 1,
      totalPages: 1
    });
    if (value !== undefined && value !== null && value !== "") {
      return String(value);
    }
  }
  return String(object.value ?? object.properties?.value ?? binding ?? "");
}

function tableSpec(object) {
  return {
    data_path: object.data_path || object.properties?.data_path || "",
    columns: normalizeTableColumns(object.columns || object.properties?.columns),
    header: {
      visible: true,
      height: 24,
      background_color: "#e5e7eb",
      color: "#111827",
      font_size: 10,
      bold: true,
      ...(object.header || object.properties?.header || {})
    },
    row: {
      height: 22,
      background_color: "#ffffff",
      alternate_background_color: "#f9fafb",
      color: "#111827",
      font_size: 10,
      ...(object.row || object.properties?.row || {})
    },
    border: {
      width: 1,
      color: "#d1d5db",
      ...(object.border || object.properties?.border || {})
    }
  };
}

function normalizeTableColumns(columns) {
  const source = Array.isArray(columns) && columns.length > 0
    ? columns
    : [
        { id: "column_1", label: "Column 1", binding: "column_1", width: 150, align: "left" },
        { id: "column_2", label: "Column 2", binding: "column_2", width: 120, align: "left" },
        { id: "column_3", label: "Column 3", binding: "column_3", width: 120, align: "left" }
      ];
  return source.map((column, index) => {
    const binding = String(column.binding || column.field || column.id || `column_${index + 1}`);
    return {
      id: String(column.id || binding),
      label: String(column.label || binding),
      binding,
      width: Math.max(20, Number(column.width) || 120),
      align: ["left", "center", "right"].includes(String(column.align)) ? String(column.align) : "left"
    };
  });
}

function tableCellValue(column, row, dataPath, sampleData) {
  const rowValue = getRowValue(row, column.binding, dataPath);
  if (rowValue !== "") {
    return String(rowValue);
  }
  const globalValue = getFieldValue(sampleData, column.binding);
  return globalValue === undefined || globalValue === null ? "" : String(globalValue);
}

function columnWidthPercent(column, columns) {
  const total = columns.reduce((sum, item) => sum + Math.max(Number(item.width) || 0, 0), 0);
  if (total <= 0) {
    return 100 / Math.max(columns.length, 1);
  }
  return Math.max(Number(column.width) || 0, 0) * 100 / total;
}

function renderRepeatedPreviewCopies(canvas, template, selectedIds, primarySelectedId, unit, repeat, rows) {
  const objects = (template.objects || []).filter((object) => objectBandId(object) === "detail");
  const rowHeight = Number(repeat.row_height) || 22;
  const count = Math.min(rows.length, Number(repeat.preview_rows) || 10);
  if (count === 0) {
    canvas.appendChild(emptyRepeatMessage(template, repeat, unit));
    return;
  }
  for (let rowIndex = 1; rowIndex < count; rowIndex += 1) {
    for (const object of objects) {
      const copy = {
        ...object,
        id: `${object.id}__repeat_${rowIndex}`,
        y: (Number(object.y) || 0) + (rowIndex * rowHeight)
      };
      canvas.appendChild(renderObject(copy, selectedIds, primarySelectedId, unit, {
        previewCopy: true,
        sampleData: template.data?.sample || {},
        showSampleData: true,
        rowData: rows[rowIndex],
        repeatDataPath: repeat.data_path
      }));
    }
  }
}

function emptyRepeatMessage(template, repeat, unit) {
  const band = (template.bands || []).find((item) => item.id === "detail") || {};
  const element = document.createElement("div");
  element.className = "repeat-empty-message";
  element.style.left = "12px";
  element.style.top = `${unitToPx((Number(band.y) || 0) + 8, unit)}px`;
  element.textContent = repeat.empty_message || "No records";
  return element;
}

function activeRepeat(template) {
  const detail = (template.bands || []).find((band) => band.id === "detail");
  if (!detail?.repeat?.enabled || !detail.repeat.data_path) {
    return null;
  }
  return detail.repeat;
}

function sampleGroupForObject(template, object) {
  const bandId = objectBandId(object);
  const band = (template.bands || []).find((item) => item.id === bandId);
  if (!["group_header", "group_footer"].includes(band?.type)) {
    return null;
  }
  const detail = (template.bands || []).find((item) => item.id === "detail") || {};
  const groupHeader = (template.bands || []).find((item) => item.type === "group_header") || band;
  const dataPath = band.group?.data_path || groupHeader.group?.data_path || detail.repeat?.data_path || "";
  const field = band.group?.field || groupHeader.group?.field || "";
  const rows = getArrayByPath(template.data?.sample || {}, dataPath);
  if (!field || rows.length === 0) {
    return { key: "", field, rows: [] };
  }
  const key = String(getRowValue(rows[0] || {}, field, dataPath) ?? "");
  return {
    key,
    field,
    rows: rows.filter((row) => String(getRowValue(row || {}, field, dataPath) ?? "") === key)
  };
}

function objectBandId(object) {
  return object?.band || object?.band_id || object?.properties?.band || "detail";
}

function objectBounds(objects, unit = "px") {
  if (!objects.length) {
    return null;
  }
  const left = Math.min(...objects.map((object) => unitToPx(object.x, unit)));
  const top = Math.min(...objects.map((object) => unitToPx(object.y, unit)));
  const right = Math.max(...objects.map((object) => unitToPx(object.x + object.width, unit)));
  const bottom = Math.max(...objects.map((object) => unitToPx(object.y + object.height, unit)));
  return {
    left,
    top,
    width: right - left,
    height: bottom - top
  };
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

function findObject(template, objectId) {
  return (template.objects || []).find((object) => object.id === objectId);
}

export function constrainedGroupDelta(items, dx, dy, template) {
  const page = template.page || {};
  const pageWidth = Number(page.width) || 595;
  let adjustedDx = dx;
  let adjustedDy = dy;
  for (const item of items) {
    const liveObject = findObject(template, item.id);
    const band = getBandForObject(template, liveObject || item);
    const bandTop = Number(band?.y) || 0;
    const bandHeight = Number(band?.height) || Number(page.height) || 842;
    const bandBottom = bandTop + bandHeight;
    adjustedDx = Math.max(adjustedDx, -item.x);
    adjustedDx = Math.min(adjustedDx, pageWidth - item.x - item.width);
    adjustedDy = Math.max(adjustedDy, bandTop - item.y);
    adjustedDy = Math.min(adjustedDy, bandBottom - item.y - item.height);
  }
  return { dx: adjustedDx, dy: adjustedDy };
}

export function placeObjectOnCanvas(object, template, settings, viewport = null) {
  const page = template.page || {};
  const unitScale = unitToPx(1, page.unit);
  const zoom = Number(settings?.zoom) || 1;
  let x = 40;
  let y = 40;
  if (viewport) {
    x = (Number(viewport.scrollLeft) || 0) / zoom / unitScale + 24;
    y = (Number(viewport.scrollTop) || 0) / zoom / unitScale + 24;
  }
  object.x = Math.round(maybeSnap(x, settings, unitScale));
  object.y = Math.round(maybeSnap(y, settings, unitScale));
  clampObjectToBand(template, object);
}

function isEditingText(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
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

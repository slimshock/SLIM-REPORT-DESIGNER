import { objectStyle } from "./objects.js";
import { gridSizeForUnit, maybeSnap, screenDeltaToRealDelta } from "./canvas_settings.js";

export function createCanvasController({
  canvas,
  getTemplate,
  getSelectedIds,
  getPrimarySelectedId,
  getCanvasSettings,
  onSelect,
  onChange,
  onCaptureHistory = () => null,
  onCommitHistory = () => {}
}) {
  let dragState = null;

  canvas.addEventListener("pointerdown", (event) => {
    const objectElement = event.target.closest(".report-object");

    if (!objectElement) {
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
    if (currentObject.locked) {
      return;
    }
    const selectedIds = getSelectedIds();
    const movingIds = resizing
      ? [objectId]
      : selectedIds.includes(objectId) ? selectedIds : [objectId];
    const movingObjects = movingIds
      .map((id) => findObject(getTemplate(), id))
      .filter((item) => item && !item.locked);
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
      if (object.locked) {
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
        clampObjectToPage(target, getTemplate());
      }
    }

    if (dragState.resizing) {
      clampObjectToPage(object, getTemplate());
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
        if (!object || object.locked) {
          continue;
        }
        object.x = Math.round((Number(object.x) || 0) + dx);
        object.y = Math.round((Number(object.y) || 0) + dy);
        clampObjectToPage(object, getTemplate());
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
      renderCanvas(canvas, getTemplate(), getSelectedIds(), getPrimarySelectedId(), getCanvasSettings());
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

export function renderCanvas(canvas, template, selectedIds = [], primarySelectedId = null, settings = {}) {
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

  for (const object of template.objects || []) {
    canvas.appendChild(renderObject(object, selectedIds, primarySelectedId, page.unit));
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

function renderObject(object, selectedIds = [], primarySelectedId = null, unit = "px") {
  const element = document.createElement("div");

  element.className = "report-object";

  if (selectedIds.includes(object.id)) {
    element.classList.add("selected");
  }
  if (object.id === primarySelectedId) {
    element.classList.add("primary-selected");
  }
  if (object.locked) {
    element.classList.add("locked");
  }

  element.dataset.objectId = object.id;
  element.dataset.type = object.type;

  element.style.left = `${unitToPx(Number(object.x) || 0, unit)}px`;
  element.style.top = `${unitToPx(Number(object.y) || 0, unit)}px`;
  element.style.width = `${unitToPx(Number(object.width) || 0, unit)}px`;
  element.style.height = `${unitToPx(Math.max(Number(object.height) || 0, object.type === "line" ? 6 : 8), unit)}px`;

  const style = objectStyle(object);

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
    element.textContent = `{{ ${object.binding || object.properties?.binding || ""} }}`;
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
    if (object.src || object.properties?.src || object.properties?.source) {
      const image = document.createElement("img");
      image.src = object.src || object.properties?.src || object.properties?.source;
      image.alt = object.alt || object.properties?.alt || "";
      image.draggable = false;
      image.style.objectFit = style.object_fit || "contain";
      element.appendChild(image);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "image-placeholder";
      placeholder.textContent = "Image";
      element.appendChild(placeholder);
    }
  }

  if (object.locked) {
    const lock = document.createElement("span");
    lock.className = "lock-indicator";
    lock.textContent = "Locked";
    element.appendChild(lock);
  }

  if (object.id === primarySelectedId && !object.locked) {
    const handle = document.createElement("div");
    handle.className = "resize-handle";
    element.appendChild(handle);
  }

  return element;
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

function clampObjectToPage(object, template) {
  const page = template.page || {};
  const pageWidth = Number(page.width) || 595;
  const pageHeight = Number(page.height) || 842;

  object.width = Math.max(8, Math.round(Number(object.width) || 8));

  if (object.type === "line") {
    object.height = Math.max(0, Math.round(Number(object.height) || 0));
  } else {
    object.height = Math.max(8, Math.round(Number(object.height) || 8));
  }

  object.x = Math.max(0, Math.round(Number(object.x) || 0));
  object.y = Math.max(0, Math.round(Number(object.y) || 0));

  if (object.x + object.width > pageWidth) {
    object.x = Math.max(0, pageWidth - object.width);
  }

  if (object.y + object.height > pageHeight) {
    object.y = Math.max(0, pageHeight - object.height);
  }
}

function constrainedGroupDelta(items, dx, dy, template) {
  const page = template.page || {};
  const pageWidth = Number(page.width) || 595;
  const pageHeight = Number(page.height) || 842;
  let adjustedDx = dx;
  let adjustedDy = dy;
  for (const item of items) {
    adjustedDx = Math.max(adjustedDx, -item.x);
    adjustedDx = Math.min(adjustedDx, pageWidth - item.x - item.width);
    adjustedDy = Math.max(adjustedDy, -item.y);
    adjustedDy = Math.min(adjustedDy, pageHeight - item.y - item.height);
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
  clampObjectToPage(object, template);
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

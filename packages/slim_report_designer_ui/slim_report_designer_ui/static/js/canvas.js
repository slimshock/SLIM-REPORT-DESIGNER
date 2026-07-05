import { objectStyle } from "./objects.js";

export function createCanvasController({ canvas, getTemplate, getSelectedId, onSelect, onChange }) {
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

    onSelect(object.id);

    const currentObject = findObject(getTemplate(), objectId);

    if (!currentObject) {
      return;
    }

    dragState = {
      objectId,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: Number(currentObject.x) || 0,
      startY: Number(currentObject.y) || 0,
      startWidth: Number(currentObject.width) || 0,
      startHeight: Number(currentObject.height) || 0,
      resizing,
      captureElement: objectElement,
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

    if (dragState.resizing) {
      object.width = Math.max(8, Math.round(dragState.startWidth + dx));
      object.height = Math.max(
        object.type === "line" ? 0 : 8,
        Math.round(dragState.startHeight + dy)
      );
    } else {
      object.x = Math.round(dragState.startX + dx);
      object.y = Math.round(dragState.startY + dy);
    }

    clampObjectToPage(object, getTemplate());
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

    const selectedId = getSelectedId();

    if (!selectedId) {
      return;
    }

    const object = findObject(getTemplate(), selectedId);

    if (!object) {
      return;
    }

    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      onSelect(selectedId, { deleteSelected: true });
      return;
    }

    const step = event.shiftKey ? 10 : 1;
    let changed = false;

    if (event.key === "ArrowLeft") {
      object.x = Math.round((Number(object.x) || 0) - step);
      changed = true;
    } else if (event.key === "ArrowRight") {
      object.x = Math.round((Number(object.x) || 0) + step);
      changed = true;
    } else if (event.key === "ArrowUp") {
      object.y = Math.round((Number(object.y) || 0) - step);
      changed = true;
    } else if (event.key === "ArrowDown") {
      object.y = Math.round((Number(object.y) || 0) + step);
      changed = true;
    }

    if (changed) {
      event.preventDefault();
      clampObjectToPage(object, getTemplate());
      onChange();
    }
  });

  return {
    render() {
      renderCanvas(canvas, getTemplate(), getSelectedId());
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

export function renderCanvas(canvas, template, selectedId) {
  const page = template.page || {};

  canvas.style.width = `${page.width || 595}px`;
  canvas.style.height = `${page.height || 842}px`;
  canvas.innerHTML = "";

  for (const object of template.objects || []) {
    canvas.appendChild(renderObject(object, selectedId));
  }
}

function renderObject(object, selectedId) {
  const element = document.createElement("div");

  element.className = "report-object";

  if (object.id === selectedId) {
    element.classList.add("selected");
  }

  element.dataset.objectId = object.id;
  element.dataset.type = object.type;

  element.style.left = `${Number(object.x) || 0}px`;
  element.style.top = `${Number(object.y) || 0}px`;
  element.style.width = `${Number(object.width) || 0}px`;
  element.style.height = `${Math.max(Number(object.height) || 0, object.type === "line" ? 6 : 8)}px`;

  const style = objectStyle(object);

  element.style.fontSize = `${Number(style.font_size) || 12}px`;
  element.style.fontWeight = style.bold ? "700" : "400";
  element.style.color = style.color || "#111827";
  element.style.textAlign = style.align || "left";

  if (object.type === "text") {
    element.textContent = object.text || object.properties?.text || "Text";
  } else if (object.type === "field") {
    element.textContent = `{{ ${object.binding || object.properties?.binding || ""} }}`;
  } else if (object.type === "line") {
    const line = document.createElement("div");
    line.className = "line-preview";
    line.style.borderTopWidth = `${Number(style.stroke_width) || 1}px`;
    element.appendChild(line);
  } else if (object.type === "rectangle") {
    const rectangle = document.createElement("div");
    rectangle.className = "rectangle-preview";
    rectangle.style.borderWidth = `${Number(style.border_width) || 1}px`;
    element.appendChild(rectangle);
  }

  if (object.id === selectedId) {
    const handle = document.createElement("div");
    handle.className = "resize-handle";
    element.appendChild(handle);
  }

  return element;
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

function isEditingText(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
}

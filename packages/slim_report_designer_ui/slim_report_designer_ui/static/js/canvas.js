import { objectStyle } from "./objects.js";

export function createCanvasController({ canvas, getTemplate, getSelectedId, onSelect, onChange }) {
  let dragState = null;

  canvas.addEventListener("pointerdown", (event) => {
    const objectElement = event.target.closest(".report-object");
    if (!objectElement) {
      onSelect(null);
      return;
    }

    const object = findObject(getTemplate(), objectElement.dataset.objectId);
    if (!object) {
      return;
    }

    onSelect(object.id);

    const resizing = event.target.classList.contains("resize-handle");
    dragState = {
      object,
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: Number(object.x) || 0,
      startY: Number(object.y) || 0,
      startWidth: Number(object.width) || 0,
      startHeight: Number(object.height) || 0,
      resizing
    };
    objectElement.setPointerCapture(event.pointerId);
    event.preventDefault();
  });

  canvas.addEventListener("pointermove", (event) => {
    if (!dragState || event.pointerId !== dragState.pointerId) {
      return;
    }
    const dx = event.clientX - dragState.startClientX;
    const dy = event.clientY - dragState.startClientY;

    if (dragState.resizing) {
      dragState.object.width = Math.max(8, Math.round(dragState.startWidth + dx));
      dragState.object.height = Math.max(
        dragState.object.type === "line" ? 0 : 8,
        Math.round(dragState.startHeight + dy)
      );
    } else {
      dragState.object.x = Math.round(dragState.startX + dx);
      dragState.object.y = Math.round(dragState.startY + dy);
    }
    onChange();
  });

  canvas.addEventListener("pointerup", (event) => {
    if (dragState && event.pointerId === dragState.pointerId) {
      dragState = null;
    }
  });

  canvas.addEventListener("keydown", (event) => {
    if (event.key === "Delete" || event.key === "Backspace") {
      const selectedId = getSelectedId();
      if (selectedId) {
        event.preventDefault();
        onSelect(selectedId, { deleteSelected: true });
      }
    }
  });

  return {
    render() {
      renderCanvas(canvas, getTemplate(), getSelectedId());
    }
  };
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

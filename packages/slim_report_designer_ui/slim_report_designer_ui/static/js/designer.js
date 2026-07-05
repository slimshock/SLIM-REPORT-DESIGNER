import { createCanvasController } from "./canvas.js";
import { createInspector } from "./inspector.js";
import {
  createObject,
  duplicateObject,
  normalizeTemplate,
  templateTitle
} from "./objects.js";
import {
  exportPdf,
  loadTemplate,
  previewTemplate,
  saveTemplate
} from "./api.js";
import { createToolbar } from "./toolbar.js";

const state = {
  template: null,
  selectedId: null
};

const elements = {
  canvas: document.querySelector("#page-canvas"),
  toolbox: document.querySelector(".toolbox"),
  inspectorForm: document.querySelector("#inspector-form"),
  toolbar: document.querySelector("#toolbar-actions"),
  status: document.querySelector("#status-message"),
  objectCount: document.querySelector("#object-count"),
  importFile: document.querySelector("#import-file"),
  templateTitle: document.querySelector("#template-title")
};

const canvasController = createCanvasController({
  canvas: elements.canvas,
  getTemplate: () => state.template,
  getSelectedId: () => state.selectedId,
  onSelect: handleCanvasSelect,
  onChange: render
});

const inspector = createInspector({
  form: elements.inspectorForm,
  getSelectedObject,
  onChange: render,
  onSelect: selectObject
});

createToolbar({
  container: elements.toolbar,
  onCommand: handleCommand
});

elements.toolbox.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tool]");
  if (!button) {
    return;
  }
  const object = createObject(button.dataset.tool, state.template);
  state.template.objects.push(object);
  selectObject(object.id);
  setStatus(`Added ${object.type}`);
  render();
});

elements.importFile.addEventListener("change", async () => {
  const file = elements.importFile.files?.[0];
  if (!file) {
    return;
  }
  try {
    const payload = JSON.parse(await file.text());
    state.template = normalizeTemplate(payload);
    state.selectedId = null;
    setStatus(`Imported ${file.name}`);
    render();
  } catch (error) {
    setStatus(error.message);
  } finally {
    elements.importFile.value = "";
  }
});

document.addEventListener("keydown", (event) => {
  if (isEditingText(event.target)) {
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
    event.preventDefault();
    duplicateSelected();
  }
});

initialize();

async function initialize() {
  try {
    state.template = normalizeTemplate(await loadTemplate());
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    state.template = normalizeTemplate({});
  }
  render();
}

async function handleCommand(command) {
  try {
    if (command === "save") {
      state.template = normalizeTemplate(await saveTemplate(state.template));
      setStatus("Saved");
    } else if (command === "preview") {
      await previewTemplate(state.template);
      setStatus("Preview opened");
    } else if (command === "exportPdf") {
      await exportPdf(state.template);
      setStatus("PDF exported");
    } else if (command === "exportJson") {
      exportJson();
    } else if (command === "importJson") {
      elements.importFile.click();
    } else if (command === "copyJson") {
      await copyJson();
    } else if (command === "duplicate") {
      duplicateSelected();
    } else if (command === "delete") {
      deleteSelected();
    }
  } catch (error) {
    setStatus(error.message);
  }
}

function handleCanvasSelect(objectId, options = {}) {
  if (options.deleteSelected) {
    deleteSelected();
    return;
  }
  selectObject(objectId);
}

function selectObject(objectId) {
  state.selectedId = objectId;
  render();
}

function getSelectedObject() {
  if (!state.selectedId) {
    return null;
  }
  return state.template.objects.find((object) => object.id === state.selectedId) || null;
}

function duplicateSelected() {
  const selected = getSelectedObject();
  if (!selected) {
    setStatus("No object selected");
    return;
  }
  const clone = duplicateObject(selected, state.template);
  state.template.objects.push(clone);
  state.selectedId = clone.id;
  setStatus(`Duplicated ${selected.id}`);
  render();
}

function deleteSelected() {
  if (!state.selectedId) {
    setStatus("No object selected");
    return;
  }
  const index = state.template.objects.findIndex((object) => object.id === state.selectedId);
  if (index >= 0) {
    const [removed] = state.template.objects.splice(index, 1);
    state.selectedId = null;
    setStatus(`Deleted ${removed.id}`);
    render();
  }
}

function exportJson() {
  const blob = new Blob([toJson()], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "report-template.json";
  link.click();
  URL.revokeObjectURL(url);
  setStatus("JSON exported");
}

async function copyJson() {
  await navigator.clipboard.writeText(toJson());
  setStatus("JSON copied");
}

function toJson() {
  return `${JSON.stringify(state.template, null, 2)}\n`;
}

function render() {
  if (!state.template) {
    return;
  }
  state.template = normalizeTemplate(state.template);
  canvasController.render();
  inspector.render();
  elements.templateTitle.textContent = templateTitle(state.template);
  const count = state.template.objects.length;
  elements.objectCount.textContent = `${count} ${count === 1 ? "object" : "objects"}`;
}

function setStatus(message) {
  elements.status.textContent = message;
}

function isEditingText(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
}

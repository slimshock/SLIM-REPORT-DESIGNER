import { createCanvasController, placeObjectOnCanvas } from "./canvas.js";
import {
  loadCanvasSettings,
  normalizeCanvasSettings,
  saveCanvasSettings,
  zoomIn,
  zoomOut
} from "./canvas_settings.js";
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
import {
  clearVersions,
  createVersion,
  deleteVersion,
  getHistoryKey,
  listVersions,
  restoreVersion
} from "./history.js";
import { applyIcon } from "./icons.js";
import { createToolbar } from "./toolbar.js";

const HISTORY_LIMIT = 50;

const state = {
  template: null,
  selectedId: null,
  canvasSettings: loadCanvasSettings(),
  undoStack: [],
  redoStack: [],
  dirty: false,
  statusMessage: "Ready"
};

const elements = {
  canvas: document.querySelector("#page-canvas"),
  canvasScroller: document.querySelector(".canvas-scroller"),
  toolbox: document.querySelector(".toolbox"),
  inspectorForm: document.querySelector("#inspector-form"),
  toolbar: document.querySelector("#toolbar-actions"),
  status: document.querySelector("#status-message"),
  selectedObject: document.querySelector("#selected-object"),
  objectCount: document.querySelector("#object-count"),
  importFile: document.querySelector("#import-file"),
  templateTitle: document.querySelector("#template-title"),
  historyModal: document.querySelector("#history-modal"),
  historyClose: document.querySelector("#history-close"),
  historyCreate: document.querySelector("#history-create"),
  historyClear: document.querySelector("#history-clear"),
  historyList: document.querySelector("#history-list"),
  historyKey: document.querySelector("#history-key")
};

const canvasController = createCanvasController({
  canvas: elements.canvas,
  getTemplate: () => state.template,
  getSelectedId: () => state.selectedId,
  getCanvasSettings: () => state.canvasSettings,
  onSelect: handleCanvasSelect,
  onChange: markDirty,
  onCaptureHistory: captureHistorySnapshot,
  onCommitHistory: commitHistorySnapshot
});

const inspector = createInspector({
  form: elements.inspectorForm,
  getTemplate: () => state.template,
  getSelectedObject,
  onBeforeChange: recordUndo,
  onChange: markDirty,
  onSelect: selectObject
});

const toolbar = createToolbar({
  container: elements.toolbar,
  onCommand: handleCommand
});

initializeToolboxIcons();
initializeHistoryUi();

elements.toolbox.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tool]");
  if (!button) {
    return;
  }
  recordUndo(`Add ${button.dataset.tool}`);
  const object = createObject(button.dataset.tool, state.template);
  placeObjectOnCanvas(object, state.template, state.canvasSettings, elements.canvasScroller);
  state.template.objects.push(object);
  selectObject(object.id);
  showActiveTool(button);
  markDirty(`Added ${object.type}`);
});

elements.importFile.addEventListener("change", async () => {
  const file = elements.importFile.files?.[0];
  if (!file) {
    return;
  }
  try {
    if (state.template) {
      createVersion(currentTemplateId(), state.template, "Before import");
      recordUndo("Import JSON");
    }
    const payload = JSON.parse(await file.text());
    state.template = normalizeTemplate(payload);
    state.selectedId = null;
    markDirty(`Imported ${file.name}`);
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
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    event.preventDefault();
    if (event.shiftKey) {
      redo();
    } else {
      undo();
    }
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y") {
    event.preventDefault();
    redo();
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

async function handleCommand(command, payload = {}) {
  try {
    if (command === "save") {
      state.template = normalizeTemplate(await saveTemplate(state.template));
      state.dirty = false;
      createVersion(currentTemplateId(), state.template, "Saved");
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
    } else if (command === "undo") {
      undo();
    } else if (command === "redo") {
      redo();
    } else if (command === "duplicate") {
      duplicateSelected();
    } else if (command === "delete") {
      deleteSelected();
    } else if (command === "history") {
      openHistory();
    } else if (command === "zoomIn") {
      updateCanvasSettings({ zoom: zoomIn(state.canvasSettings.zoom) });
    } else if (command === "zoomOut") {
      updateCanvasSettings({ zoom: zoomOut(state.canvasSettings.zoom) });
    } else if (command === "resetZoom") {
      updateCanvasSettings({ zoom: 1 });
    } else if (command === "fitPage") {
      fitPage();
    } else if (command === "canvasSetting") {
      updateCanvasSettings({ [payload.key]: payload.value });
    }
  } catch (error) {
    setStatus(error.message);
  }
}

function updateCanvasSettings(patch) {
  state.canvasSettings = normalizeCanvasSettings({
    ...state.canvasSettings,
    ...patch
  });
  saveCanvasSettings(state.canvasSettings);
  setStatus("Canvas settings updated");
  render();
}

function fitPage() {
  const page = state.template?.page || {};
  const scroller = elements.canvasScroller;
  if (!scroller) {
    updateCanvasSettings({ zoom: 1 });
    return;
  }
  const pageWidth = unitToPx(page.width || 595, page.unit);
  const pageHeight = unitToPx(page.height || 842, page.unit);
  const availableWidth = Math.max(scroller.clientWidth - 96, 100);
  const availableHeight = Math.max(scroller.clientHeight - 96, 100);
  const zoom = Math.min(availableWidth / pageWidth, availableHeight / pageHeight, 2);
  updateCanvasSettings({ zoom: Math.max(0.25, zoom) });
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
  recordUndo(`Duplicate ${selected.id}`);
  const clone = duplicateObject(selected, state.template);
  state.template.objects.push(clone);
  state.selectedId = clone.id;
  markDirty(`Duplicated ${selected.id}`);
}

function deleteSelected() {
  if (!state.selectedId) {
    setStatus("No object selected");
    return;
  }
  const index = state.template.objects.findIndex((object) => object.id === state.selectedId);
  if (index >= 0) {
    recordUndo(`Delete ${state.selectedId}`);
    const [removed] = state.template.objects.splice(index, 1);
    state.selectedId = null;
    markDirty(`Deleted ${removed.id}`);
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

function initializeToolboxIcons() {
  for (const item of elements.toolbox.querySelectorAll("[data-icon]")) {
    applyIcon(item, item.dataset.icon);
  }
}

function initializeHistoryUi() {
  applyIcon(elements.historyClose, "close");
  elements.historyClose.addEventListener("click", closeHistory);
  elements.historyModal.addEventListener("click", (event) => {
    if (event.target === elements.historyModal) {
      closeHistory();
    }
  });
  elements.historyCreate.addEventListener("click", () => {
    createVersion(currentTemplateId(), state.template, "Manual version");
    setStatus("Version created");
    renderHistory();
  });
  elements.historyClear.addEventListener("click", () => {
    if (!confirm("Clear local version history for this template?")) {
      return;
    }
    clearVersions(currentTemplateId());
    setStatus("Version history cleared");
    renderHistory();
  });
  elements.historyList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-version-command]");
    if (!button) {
      return;
    }
    const versionId = button.closest("[data-version-id]")?.dataset.versionId;
    if (!versionId) {
      return;
    }
    if (button.dataset.versionCommand === "restore") {
      restoreHistoricalVersion(versionId);
    } else if (button.dataset.versionCommand === "delete") {
      deleteVersion(currentTemplateId(), versionId);
      setStatus("Version deleted");
      renderHistory();
    }
  });
}

function openHistory() {
  renderHistory();
  elements.historyModal.hidden = false;
}

function closeHistory() {
  elements.historyModal.hidden = true;
}

function renderHistory() {
  const templateId = currentTemplateId();
  const versions = listVersions(templateId);
  elements.historyKey.textContent = getHistoryKey(templateId);
  elements.historyList.innerHTML = "";
  if (versions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No local versions for this template yet.";
    elements.historyList.appendChild(empty);
    return;
  }
  for (const version of versions) {
    elements.historyList.appendChild(historyItem(version));
  }
}

function historyItem(version) {
  const item = document.createElement("article");
  item.className = "history-item";
  item.dataset.versionId = version.id;

  const details = document.createElement("div");
  details.className = "history-item-details";

  const label = document.createElement("strong");
  label.textContent = version.label || "Version";

  const meta = document.createElement("span");
  meta.textContent = `${formatDate(version.created_at)} - ${version.object_count} ${version.object_count === 1 ? "object" : "objects"}`;

  details.append(label, meta);

  const actions = document.createElement("div");
  actions.className = "history-item-actions";
  actions.append(
    historyButton("restore", "Restore", "Restore version"),
    historyButton("delete", "Delete", "Delete version", "danger")
  );

  item.append(details, actions);
  return item;
}

function historyButton(command, label, title, variant = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `toolbar-button ${variant}`.trim();
  button.dataset.versionCommand = command;
  button.title = title;
  button.textContent = label;
  return button;
}

function restoreHistoricalVersion(versionId) {
  const templateId = currentTemplateId();
  const version = listVersions(templateId).find((item) => item.id === versionId);
  const restored = restoreVersion(templateId, versionId);
  if (!restored) {
    setStatus("Version not found");
    return;
  }
  createVersion(templateId, state.template, "Before restore");
  recordUndo("Restore version");
  state.template = normalizeTemplate(restored);
  state.selectedId = null;
  markDirty(`Restored version from ${formatDate(version?.created_at)}`);
  renderHistory();
}

function currentTemplateId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("template") || state.template?.metadata?.custom?.id || state.template?.metadata?.name || "default";
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "unknown date";
}

function render(options = {}) {
  if (!state.template) {
    return;
  }
  state.template = normalizeTemplate(state.template);
  canvasController.render();
  if (!options.preserveInspector) {
    inspector.render();
  }
  toolbar.render({
    hasSelection: Boolean(getSelectedObject()),
    canvasSettings: state.canvasSettings,
    canUndo: state.undoStack.length > 0,
    canRedo: state.redoStack.length > 0
  });
  elements.templateTitle.textContent = templateTitle(state.template);
  const count = state.template.objects.length;
  elements.objectCount.textContent = `${count} ${count === 1 ? "object" : "objects"} | ${canvasInfoLabel()}`;
  elements.selectedObject.textContent = selectedObjectLabel();
  elements.status.textContent = statusLabel();
}

function setStatus(message) {
  state.statusMessage = message;
  elements.status.textContent = statusLabel();
}

function markDirty(message = "Unsaved changes", options = {}) {
  if (typeof message === "object" && message !== null) {
    options = message;
    message = "Unsaved changes";
  }
  state.dirty = true;
  state.statusMessage = message;
  render(options);
}

function captureHistorySnapshot() {
  return state.template ? structuredClone(state.template) : null;
}

function commitHistorySnapshot(snapshot, label = "Edit") {
  if (!snapshot || !state.template || templatesEqual(snapshot, state.template)) {
    return;
  }
  pushUndoSnapshot(snapshot, label);
  state.redoStack = [];
  render();
}

function recordUndo(label = "Edit") {
  const snapshot = captureHistorySnapshot();
  if (!snapshot) {
    return;
  }
  pushUndoSnapshot(snapshot, label);
  state.redoStack = [];
}

function pushUndoSnapshot(snapshot, label) {
  const previous = state.undoStack[state.undoStack.length - 1];
  if (previous && templatesEqual(previous.template, snapshot)) {
    previous.label = label;
    return;
  }
  state.undoStack.push({ label, template: snapshot });
  if (state.undoStack.length > HISTORY_LIMIT) {
    state.undoStack.shift();
  }
}

function undo() {
  const entry = state.undoStack.pop();
  if (!entry) {
    setStatus("Nothing to undo");
    render();
    return;
  }
  state.redoStack.push({
    label: "Redo",
    template: captureHistorySnapshot()
  });
  restoreTemplateSnapshot(entry.template);
  state.dirty = true;
  state.statusMessage = `Undid ${entry.label}`;
  render();
}

function redo() {
  const entry = state.redoStack.pop();
  if (!entry) {
    setStatus("Nothing to redo");
    render();
    return;
  }
  state.undoStack.push({
    label: "Undo redo",
    template: captureHistorySnapshot()
  });
  restoreTemplateSnapshot(entry.template);
  state.dirty = true;
  state.statusMessage = "Redid change";
  render();
}

function restoreTemplateSnapshot(snapshot) {
  state.template = normalizeTemplate(structuredClone(snapshot));
  if (state.selectedId && !state.template.objects.some((object) => object.id === state.selectedId)) {
    state.selectedId = null;
  }
}

function templatesEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function statusLabel() {
  if (!state.dirty) {
    return state.statusMessage;
  }
  if (!state.statusMessage || state.statusMessage === "Unsaved changes") {
    return "Unsaved changes";
  }
  return `Unsaved changes - ${state.statusMessage}`;
}

function selectedObjectLabel() {
  const selected = getSelectedObject();
  if (!selected) {
    return "No selection";
  }
  return `Selected: ${selected.type} ${selected.id}`;
}

function canvasInfoLabel() {
  const settings = state.canvasSettings;
  return `Grid: ${settings.grid_size}px | Zoom: ${Math.round(settings.zoom * 100)}% | Snap: ${settings.snap_to_grid ? "On" : "Off"}`;
}

function showActiveTool(button) {
  for (const item of elements.toolbox.querySelectorAll(".tool-button.is-active")) {
    item.classList.remove("is-active");
  }
  button.classList.add("is-active");
  setTimeout(() => button.classList.remove("is-active"), 700);
}

function isEditingText(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
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

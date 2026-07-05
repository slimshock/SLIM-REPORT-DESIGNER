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
  assignObjectBand,
  clampObjectToBand,
  duplicateObject,
  getBandById,
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
  selectedIds: [],
  primarySelectedId: null,
  activeBandId: "detail",
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
  getSelectedIds: () => state.selectedIds,
  getPrimarySelectedId: () => state.primarySelectedId,
  getActiveBandId: () => state.activeBandId,
  getCanvasSettings: () => state.canvasSettings,
  onSelect: handleCanvasSelect,
  onSelectBand: selectBand,
  onChange: markDirty,
  onCaptureHistory: captureHistorySnapshot,
  onCommitHistory: commitHistorySnapshot
});

const inspector = createInspector({
  form: elements.inspectorForm,
  getTemplate: () => state.template,
  getSelectedObject,
  getSelectedObjects,
  getActiveBandId: () => state.activeBandId,
  onBeforeChange: recordUndo,
  onChange: markDirty,
  onCommand: handleCommand,
  onSelect: selectObject,
  onSelectBand: selectBand
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
  assignObjectBand(state.template, object, state.activeBandId);
  placeObjectOnCanvas(object, state.template, state.canvasSettings, elements.canvasScroller);
  clampObjectToBand(state.template, object);
  state.template.objects.push(object);
  selectOnly(object.id);
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
    ensureActiveBand();
    clearSelection();
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
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
    event.preventDefault();
    selectAll();
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    clearSelection();
  }
});

initialize();

async function initialize() {
  try {
    state.template = normalizeTemplate(await loadTemplate());
    ensureActiveBand();
    setStatus("Ready");
  } catch (error) {
    setStatus(error.message);
    state.template = normalizeTemplate({});
    ensureActiveBand();
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
    } else if (command.startsWith("align")) {
      alignSelected(command.replace("align", "").toLowerCase());
    } else if (command === "distributeHorizontal") {
      distributeSelected("horizontal");
    } else if (command === "distributeVertical") {
      distributeSelected("vertical");
    } else if (command === "bringForward") {
      reorderSelected("forward");
    } else if (command === "sendBackward") {
      reorderSelected("backward");
    } else if (command === "bringToFront") {
      reorderSelected("front");
    } else if (command === "sendToBack") {
      reorderSelected("back");
    } else if (command === "lockSelected") {
      setLockedSelected(true);
    } else if (command === "unlockSelected") {
      setLockedSelected(false);
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
    } else if (command === "activeBand") {
      selectBand(payload.bandId);
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
  selectObject(objectId, options);
}

function selectObject(objectId, options = {}) {
  if (!objectId) {
    clearSelection();
    return;
  }
  if (options.toggle) {
    toggleSelection(objectId);
    return;
  }
  selectOnly(objectId);
}

function selectOnly(objectId) {
  state.selectedIds = objectId ? [objectId] : [];
  state.primarySelectedId = objectId || null;
  render();
}

function toggleSelection(objectId) {
  if (state.selectedIds.includes(objectId)) {
    state.selectedIds = state.selectedIds.filter((id) => id !== objectId);
    if (state.primarySelectedId === objectId) {
      state.primarySelectedId = state.selectedIds[state.selectedIds.length - 1] || null;
    }
  } else {
    state.selectedIds = [...state.selectedIds, objectId];
    state.primarySelectedId = objectId;
  }
  render();
}

function clearSelection() {
  state.selectedIds = [];
  state.primarySelectedId = null;
  render();
}

function selectAll() {
  state.selectedIds = state.template.objects.map((object) => object.id);
  state.primarySelectedId = state.selectedIds[state.selectedIds.length - 1] || null;
  render();
}

function selectBand(bandId) {
  if (!getBandById(state.template, bandId)) {
    return;
  }
  state.activeBandId = bandId;
  setStatus(`Active band: ${bandLabel(bandId)}`);
  render();
}

function getSelectedObject() {
  if (!state.primarySelectedId || state.selectedIds.length !== 1) {
    return null;
  }
  return state.template.objects.find((object) => object.id === state.primarySelectedId) || null;
}

function getSelectedObjects() {
  const selected = new Set(state.selectedIds);
  return state.template.objects.filter((object) => selected.has(object.id));
}

function duplicateSelected() {
  const selectedObjects = getSelectedObjects();
  if (selectedObjects.length === 0) {
    setStatus("No object selected");
    return;
  }
  recordUndo("Duplicate selected");
  const clones = [];
  for (const object of selectedObjects) {
    const clone = duplicateObject(object, {
      objects: state.template.objects.concat(clones)
    });
    clone.x += 10;
    clone.y += 10;
    clampObjectToBand(state.template, clone);
    clones.push(clone);
  }
  state.template.objects.push(...clones);
  state.selectedIds = clones.map((object) => object.id);
  state.primarySelectedId = state.selectedIds[state.selectedIds.length - 1] || null;
  markDirty(`Duplicated ${clones.length} ${clones.length === 1 ? "object" : "objects"}`);
}

function deleteSelected() {
  if (state.selectedIds.length === 0) {
    setStatus("No object selected");
    return;
  }
  recordUndo("Delete selected");
  const selected = new Set(state.selectedIds);
  const count = state.template.objects.filter((object) => selected.has(object.id)).length;
  state.template.objects = state.template.objects.filter((object) => !selected.has(object.id));
  state.selectedIds = [];
  state.primarySelectedId = null;
  markDirty(`Deleted ${count} ${count === 1 ? "object" : "objects"}`);
}

function alignSelected(kind) {
  const selected = getSelectedObjects();
  if (selected.length < 2) {
    setStatus("Select at least 2 objects");
    return;
  }
  recordUndo(`Align ${kind}`);
  const bounds = selectionBounds(selected);
  for (const object of selected.filter((item) => !item.locked && !getBandById(state.template, item.band)?.locked)) {
    if (kind === "left") {
      object.x = bounds.left;
    } else if (kind === "center") {
      object.x = Math.round(bounds.centerX - object.width / 2);
    } else if (kind === "right") {
      object.x = bounds.right - object.width;
    } else if (kind === "top") {
      object.y = bounds.top;
    } else if (kind === "middle") {
      object.y = Math.round(bounds.centerY - object.height / 2);
    } else if (kind === "bottom") {
      object.y = bounds.bottom - object.height;
    }
    clampObjectToBand(state.template, object);
  }
  markDirty(`Aligned ${selected.length} objects`);
}

function distributeSelected(axis) {
  const selected = getSelectedObjects().filter((object) => !object.locked && !getBandById(state.template, object.band)?.locked);
  if (selected.length < 3) {
    setStatus("Select at least 3 unlocked objects");
    return;
  }
  recordUndo(`Distribute ${axis}`);
  const key = axis === "horizontal" ? "x" : "y";
  const sizeKey = axis === "horizontal" ? "width" : "height";
  selected.sort((a, b) => a[key] - b[key]);
  const first = selected[0];
  const last = selected[selected.length - 1];
  const available = (last[key] + last[sizeKey]) - first[key];
  const totalSize = selected.reduce((sum, object) => sum + object[sizeKey], 0);
  const gap = (available - totalSize) / (selected.length - 1);
  let cursor = first[key] + first[sizeKey] + gap;
  for (const object of selected.slice(1, -1)) {
    object[key] = Math.round(cursor);
    clampObjectToBand(state.template, object);
    cursor += object[sizeKey] + gap;
  }
  markDirty(`Distributed ${selected.length} objects`);
}

function reorderSelected(direction) {
  const selected = new Set(state.selectedIds);
  if (selected.size === 0) {
    setStatus("No object selected");
    return;
  }
  recordUndo(`Layer ${direction}`);
  const objects = state.template.objects;
  if (direction === "front" || direction === "back") {
    const selectedObjects = objects.filter((object) => selected.has(object.id));
    const remaining = objects.filter((object) => !selected.has(object.id));
    state.template.objects = direction === "front"
      ? [...remaining, ...selectedObjects]
      : [...selectedObjects, ...remaining];
  } else if (direction === "forward") {
    for (let index = objects.length - 2; index >= 0; index -= 1) {
      if (selected.has(objects[index].id) && !selected.has(objects[index + 1].id)) {
        [objects[index], objects[index + 1]] = [objects[index + 1], objects[index]];
      }
    }
  } else if (direction === "backward") {
    for (let index = 1; index < objects.length; index += 1) {
      if (selected.has(objects[index].id) && !selected.has(objects[index - 1].id)) {
        [objects[index], objects[index - 1]] = [objects[index - 1], objects[index]];
      }
    }
  }
  markDirty("Layer order changed");
}

function setLockedSelected(locked) {
  const selected = getSelectedObjects();
  if (selected.length === 0) {
    setStatus("No object selected");
    return;
  }
  recordUndo(locked ? "Lock selected" : "Unlock selected");
  for (const object of selected) {
    object.locked = locked;
    object.properties = object.properties || {};
    object.properties.locked = locked;
  }
  markDirty(locked ? "Locked selected" : "Unlocked selected");
}

function selectionBounds(objects) {
  const left = Math.min(...objects.map((object) => object.x));
  const top = Math.min(...objects.map((object) => object.y));
  const right = Math.max(...objects.map((object) => object.x + object.width));
  const bottom = Math.max(...objects.map((object) => object.y + object.height));
  return {
    left,
    top,
    right,
    bottom,
    centerX: left + (right - left) / 2,
    centerY: top + (bottom - top) / 2
  };
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
  state.selectedIds = [];
  state.primarySelectedId = null;
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
  ensureActiveBand();
  canvasController.render();
  if (!options.preserveInspector) {
    inspector.render();
  }
  toolbar.render({
    hasSelection: state.selectedIds.length > 0,
    selectionCount: state.selectedIds.length,
    canvasSettings: state.canvasSettings,
    activeBandId: state.activeBandId,
    bands: state.template.bands || [],
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
  ensureActiveBand();
  const existing = new Set(state.template.objects.map((object) => object.id));
  state.selectedIds = state.selectedIds.filter((id) => existing.has(id));
  if (!state.primarySelectedId || !existing.has(state.primarySelectedId)) {
    state.primarySelectedId = state.selectedIds[state.selectedIds.length - 1] || null;
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
  const selected = getSelectedObjects();
  if (selected.length === 0) {
    return `Page selected | Active band: ${bandLabel(state.activeBandId)}`;
  }
  if (selected.length > 1) {
    return `Selected: ${selected.length} objects`;
  }
  return `Selected: ${selected[0].type} ${selected[0].id} | Band: ${bandLabel(selected[0].band)}`;
}

function canvasInfoLabel() {
  const settings = state.canvasSettings;
  return `Band: ${bandLabel(state.activeBandId)} | Grid: ${settings.grid_size}px | Zoom: ${Math.round(settings.zoom * 100)}% | Snap: ${settings.snap_to_grid ? "On" : "Off"}`;
}

function ensureActiveBand() {
  if (!state.template) {
    return;
  }
  if (!getBandById(state.template, state.activeBandId)) {
    state.activeBandId = getBandById(state.template, "detail")?.id || state.template.bands?.[0]?.id || "detail";
  }
}

function bandLabel(bandId) {
  const band = getBandById(state.template, bandId);
  return band?.name || bandId || "Detail";
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

import { runtimeConfig } from "./runtime_config.js";
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
  addGroupBands,
  assignObjectBand,
  clampObjectToBand,
  clearDatasetFieldBinding,
  clearEmptyBandDatasetContexts,
  duplicateObject,
  datasetFieldBindingStatus,
  datasetFieldDragPayload,
  datasetFieldObjectDefaults,
  getBandById,
  getBandDatasetId,
  getDatasetById,
  getDatasetFieldBinding,
  normalizeTemplate,
  parseDatasetFieldDragPayload,
  setDatasetFieldBinding,
  setObjectBinding,
  setObjectStyleValue,
  templateTitle
} from "./objects.js";
import {
  getFieldValue,
  getTemplateFields,
  inferFieldsFromSample,
  normalizeFieldPath,
  relativeFieldPathForCollection
} from "./data_fields.js";
import {
  exportPdf,
  inspectPreviewReadiness,
  inspectReopenedTemplate,
  loadFieldCatalog,
  loadTemplate,
  printPreview,
  previewTemplate,
  saveTemplate,
  validateTemplateSave
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
import { createDataSourceManager } from "./data_sources.js";
import { createDatasetManager } from "./datasets.js";
import { createNewReportWizard } from "./new_report_wizard.js";
import { createRuntimeParameterDialog } from "./runtime_parameters.js";
import { createLivePreview } from "./live_preview.js";
import { rotateReportSessionKey, safeTemplateSnapshot } from "./persistence.js";

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
  statusMessage: "Ready",
  collapsedDatasetIds: new Set(),
  selectedDatasetField: null,
  hostFields: []
};

const elements = {
  canvas: document.querySelector("#page-canvas"),
  canvasScroller: document.querySelector(".canvas-scroller"),
  toolbox: document.querySelector(".toolbox"),
  fieldSearch: document.querySelector("#field-search"),
  fieldSearchClear: document.querySelector("#field-search-clear"),
  fieldsList: document.querySelector("#fields-list"),
  datasetFieldInsert: document.querySelector("#dataset-field-insert"),
  datasetManagerOpen: document.querySelector("#dataset-manager-open"),
  sampleDataOpen: document.querySelector("#sample-data-open"),
  sampleDataModal: document.querySelector("#sample-data-modal"),
  sampleDataClose: document.querySelector("#sample-data-close"),
  sampleDataApply: document.querySelector("#sample-data-apply"),
  sampleDataJson: document.querySelector("#sample-data-json"),
  sampleDataError: document.querySelector("#sample-data-error"),
  inspectorForm: document.querySelector("#inspector-form"),
  toolbar: document.querySelector("#toolbar-actions"),
  status: document.querySelector("#status-message"),
  selectedObject: document.querySelector("#selected-object"),
  objectCount: document.querySelector("#object-count"),
  importFile: document.querySelector("#import-file"),
  templateTitle: document.querySelector("#template-title"),
  brandMark: document.querySelector("#designer-brand-mark"),
  brandName: document.querySelector("#designer-brand-name"),
  backLink: document.querySelector("#designer-back-link"),
  historyModal: document.querySelector("#history-modal"),
  historyClose: document.querySelector("#history-close"),
  historyCreate: document.querySelector("#history-create"),
  historyClear: document.querySelector("#history-clear"),
  historyList: document.querySelector("#history-list"),
  historyKey: document.querySelector("#history-key"),
  dataSourceModal: document.querySelector("#data-source-modal"),
  datasetModal: document.querySelector("#dataset-modal"),
  runtimeParameterModal: document.querySelector("#runtime-parameter-modal"),
  livePreviewModal: document.querySelector("#live-preview-modal"),
  newReportModal: document.querySelector("#new-report-modal")
};

const runtime = runtimeConfig();

elements.reportAttention = document.querySelector("#report-attention");
elements.reportAttentionMessage = document.querySelector("#report-attention-message");
elements.reportAttentionDataSources = document.querySelector("#report-attention-data-sources");
elements.reportAttentionDatasets = document.querySelector("#report-attention-datasets");
elements.reportAttentionDismiss = document.querySelector("#report-attention-dismiss");
elements.saveWarningModal = document.querySelector("#save-warning-modal");
elements.saveWarningList = document.querySelector("#save-warning-list");
elements.saveWarningReview = document.querySelector("#save-warning-review");
elements.saveWarningCancel = document.querySelector("#save-warning-cancel");
elements.saveWarningConfirm = document.querySelector("#save-warning-confirm");

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
  getFields: () => availableTemplateFields(),
  getSampleData: () => state.template?.data?.sample || {},
  onBeforeChange: recordUndo,
  onChange: markDirty,
  onCommand: handleCommand,
  onSelect: selectObject,
  onSelectBand: selectBand
});

const hiddenToolbarCommands = [];

if (!runtime.databaseDataSourcesEnabled) {
  hiddenToolbarCommands.push("dataSources");
}

if (!runtime.sqlDatasetsEnabled) {
  hiddenToolbarCommands.push("datasets");
}

const toolbar = createToolbar({
  container: elements.toolbar,
  onCommand: handleCommand,
  hiddenCommands: hiddenToolbarCommands
});

const dataSourceManager = createDataSourceManager({
  root: elements.dataSourceModal,
  getTemplate: () => state.template,
  onTemplateChange: applyDataSourceTemplate,
  onStatus: setStatus
});

const runtimeParameterDialog = createRuntimeParameterDialog({
  root: elements.runtimeParameterModal,
  getTemplate: () => state.template,
  onStatus: setStatus
});

const livePreview = createLivePreview({
  root: elements.livePreviewModal,
  getTemplate: () => state.template,
  onStatus: setStatus
});

const datasetManager = createDatasetManager({
  root: elements.datasetModal,
  getTemplate: () => state.template,
  onTemplateChange: applyDataSourceTemplate,
  onStatus: setStatus,
  openDataSources: () => dataSourceManager.open(
    elements.toolbar.querySelector('[data-command="dataSources"]')
  ),
  openParameters: (datasetId, openingControl) => runtimeParameterDialog.open(
    datasetId,
    { openingControl }
  ),
  enabled: runtime.sqlDatasetsEnabled,
  dataSourcesEnabled: runtime.databaseDataSourcesEnabled
});

const newReportWizard = createNewReportWizard({
  root: elements.newReportModal,
  getTemplate: () => state.template,
  isDirty: () => state.dirty,
  onSave: saveCurrentReport,
  onCreate: loadCreatedReport,
  onStatus: setStatus,
  databaseDataSourcesEnabled: runtime.databaseDataSourcesEnabled,
  sqlDatasetsEnabled: runtime.sqlDatasetsEnabled
});
applyIcon(elements.newReportModal.querySelector("#new-report-close"), "close");
applyIcon(elements.reportAttentionDismiss, "close");
elements.reportAttentionDismiss.addEventListener("click", () => {
  elements.reportAttention.hidden = true;
});

elements.reportAttentionDataSources.addEventListener("click", () => {
  if (!runtime.databaseDataSourcesEnabled) {
    return;
  }

  dataSourceManager.open(elements.reportAttentionDataSources);
});

elements.reportAttentionDatasets.addEventListener("click", () => {
  if (!runtime.sqlDatasetsEnabled) {
    return;
  }

  datasetManager.open(elements.reportAttentionDatasets);
});

function applyFeatureVisibility() {
  elements.datasetManagerOpen.hidden = !runtime.sqlDatasetsEnabled;
  elements.datasetFieldInsert.hidden = !runtime.sqlDatasetsEnabled;
}

applyFeatureVisibility();
applyHostBranding();
initializeToolboxIcons();
initializeHistoryUi();
initializeSampleDataUi();

elements.toolbox.addEventListener("click", (event) => {
  const tab = event.target.closest("button[data-panel-tab]");
  if (tab) {
    showLeftPanel(tab.dataset.panelTab);
    return;
  }
  const datasetToggle = event.target.closest("button[data-dataset-toggle]");
  if (datasetToggle) {
    const datasetId = datasetToggle.dataset.datasetToggle;
    if (state.collapsedDatasetIds.has(datasetId)) {
      state.collapsedDatasetIds.delete(datasetId);
    } else {
      state.collapsedDatasetIds.add(datasetId);
    }
    renderFieldsPanel();
    return;
  }
  const datasetField = event.target.closest("button[data-dataset-field]");
  if (datasetField && !datasetField.disabled) {
    selectDatasetFieldButton(datasetField);
    return;
  }
  const fieldsAction = event.target.closest("button[data-fields-action]");
  if (
    fieldsAction?.dataset.fieldsAction === "dataSources"
    && runtime.databaseDataSourcesEnabled
  ) {
    void dataSourceManager.open(fieldsAction);
    return;
  }

  if (
    fieldsAction?.dataset.fieldsAction === "datasets"
    && runtime.sqlDatasetsEnabled
  ) {
    void datasetManager.open(fieldsAction);
    return;
  }
  const fieldButton = event.target.closest("button[data-field-path]");
  if (fieldButton) {
    addFieldObject(fieldButton.dataset.fieldPath);
    return;
  }
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

elements.toolbox.addEventListener("dragstart", (event) => {
  const datasetField = event.target.closest("button[data-dataset-field]");
  if (datasetField && !datasetField.disabled && event.dataTransfer) {
    const payload = datasetFieldDragPayload(
      datasetField.dataset.datasetId,
      datasetField.dataset.fieldName,
      datasetField.dataset.dataType
    );
    event.dataTransfer.setData("application/x-slim-report-dataset-field", payload);
    event.dataTransfer.setData(
      "text/plain",
      `${datasetField.dataset.datasetId}.${datasetField.dataset.fieldName}`
    );
    event.dataTransfer.effectAllowed = "copy";
    datasetField.classList.add("is-dragging");
    return;
  }
  const fieldButton = event.target.closest("button[data-field-path]");
  if (!fieldButton || !event.dataTransfer) {
    return;
  }
  event.dataTransfer.setData("application/x-slim-report-field", fieldButton.dataset.fieldPath);
  event.dataTransfer.effectAllowed = "copy";
});

elements.toolbox.addEventListener("dragend", (event) => {
  event.target.closest("button[data-dataset-field]")?.classList.remove("is-dragging");
  elements.canvas.classList.remove("is-dataset-field-drop-target");
});

elements.toolbox.addEventListener("dblclick", (event) => {
  const datasetField = event.target.closest("button[data-dataset-field]");
  if (!datasetField || datasetField.disabled) {
    return;
  }
  selectDatasetFieldButton(datasetField);
  insertSelectedDatasetField();
});

elements.toolbox.addEventListener("keydown", (event) => {
  const datasetToggle = event.target.closest("button[data-dataset-toggle]");
  if (datasetToggle && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    const collapsed = state.collapsedDatasetIds.has(datasetToggle.dataset.datasetToggle);
    const shouldCollapse = event.key === "ArrowLeft";
    if (collapsed !== shouldCollapse) {
      datasetToggle.click();
    }
    event.preventDefault();
    return;
  }
  const datasetField = event.target.closest("button[data-dataset-field]");
  if (!datasetField || datasetField.disabled || !["Enter", " "].includes(event.key)) {
    return;
  }
  event.preventDefault();
  selectDatasetFieldButton(datasetField);
  insertSelectedDatasetField();
});

elements.canvas.addEventListener("dragover", (event) => {
  if (event.dataTransfer?.types.includes("application/x-slim-report-dataset-field")) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    elements.canvas.classList.add("is-dataset-field-drop-target");
    return;
  }
  if (!event.dataTransfer?.types.includes("application/x-slim-report-field")) {
    return;
  }
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});

elements.canvas.addEventListener("drop", (event) => {
  const datasetPayload = parseDatasetFieldDragPayload(
    event.dataTransfer?.getData("application/x-slim-report-dataset-field")
  );
  if (datasetPayload) {
    event.preventDefault();
    elements.canvas.classList.remove("is-dataset-field-drop-target");
    addDatasetFieldObject(datasetPayload, canvasDropPosition(event));
    return;
  }
  const path = event.dataTransfer?.getData("application/x-slim-report-field");
  if (!path) {
    return;
  }
  event.preventDefault();
  addFieldObject(path, canvasDropPosition(event));
});

elements.fieldSearch.addEventListener("input", () => renderFieldsPanel());
elements.fieldSearchClear.addEventListener("click", () => {
  elements.fieldSearch.value = "";
  elements.fieldSearch.focus();
  renderFieldsPanel();
});
elements.datasetFieldInsert.addEventListener("click", insertSelectedDatasetField);
elements.datasetManagerOpen.addEventListener("click", async () => {
  if (!runtime.sqlDatasetsEnabled) {
    return;
  }

  await datasetManager.open(elements.datasetManagerOpen);
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
    await dataSourceManager.clearRuntimePasswords();
    rotateReportSessionKey();
    state.template = normalizeTemplate(safeTemplateSnapshot(payload));
    state.hostFields = [];
    ensureActiveBand();
    try {
      await refreshHostFieldCatalog();
    } catch (error) {
      setStatus(`Host field catalog unavailable: ${error.message}`);
    }
    clearSelection();
    markDirty(`Imported ${file.name}`);
  } catch (error) {
    setStatus(error.message);
  } finally {
    elements.importFile.value = "";
  }
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
    event.preventDefault();
    newReportWizard.open(elements.toolbar.querySelector('[data-command="newReport"]'));
    return;
  }
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

function applyHostBranding() {
  const config = runtimeConfig();

  if (config.brandMark) {
    elements.brandMark.textContent = config.brandMark;
  }

  if (config.brandName) {
    elements.brandName.textContent = config.brandName;
  }

  if (config.pageTitle) {
    document.title = config.pageTitle;
  }

  if (config.backUrl) {
    elements.backLink.href = config.backUrl;
    elements.backLink.textContent = config.backLabel || "Back";
    elements.backLink.hidden = false;
  }
}

async function initialize() {
  try {
    state.template = normalizeTemplate(await loadTemplate());
    ensureActiveBand();

    let fieldCatalogWarning = "";
    try {
      await refreshHostFieldCatalog();
    } catch (error) {
      fieldCatalogWarning = `Host field catalog unavailable: ${error.message}`;
    }

    setStatus(fieldCatalogWarning || "Ready");
    await inspectCurrentReport();
  } catch (error) {
    setStatus(error.message);
    state.template = normalizeTemplate({});
    state.hostFields = [];
    ensureActiveBand();
  }
  render();
}

async function handleCommand(command, payload = {}) {
  if (command === "dataSources" && !runtime.databaseDataSourcesEnabled) {
    setStatus("Data source management is disabled.");
    return;
  }

  if (command === "datasets" && !runtime.sqlDatasetsEnabled) {
    setStatus("SQL dataset management is disabled.");
    return;
  }

  try {
    if (command === "save") {
      await saveCurrentReport();
    } else if (command === "newReport") {
      newReportWizard.open(elements.toolbar.querySelector('[data-command="newReport"]'));
    } else if (command === "preview") {
      await previewReport(payload.openingControl);
    } else if (command === "printPreview") {
      await printPreview(state.template);
      setStatus("Print preview opened");
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
    } else if (command === "dataSources") {
      await dataSourceManager.open(
        elements.toolbar.querySelector('[data-command="dataSources"]')
      );
    } else if (command === "datasets") {
      await datasetManager.open(
        elements.toolbar.querySelector('[data-command="datasets"]')
      );
    } else if (command === "chooseField") {
      showLeftPanel("fields");
      elements.fieldSearch.focus();
      setStatus("Choose a field from the Fields panel");
    } else if (command === "clearDatasetBinding") {
      const object = getSelectedObject();
      if (object && getDatasetFieldBinding(object)) {
        recordUndo("Clear data binding");
        clearDatasetFieldBinding(state.template, object);
        markDirty("Data binding cleared");
      }
    } else if (command === "addGroup") {
      addGroup();
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

async function previewReport(openingControl = null) {
  const dataset = primaryRuntimeDataset(state.template);
  if (!dataset) {
    await previewTemplate(state.template);
    setStatus("Preview opened");
    return;
  }
  const readiness = await inspectPreviewReadiness(state.template, dataset.id);
  if (!readiness.ready) {
    showReportAttention(readiness.issues);
    setStatus("Live preview is unavailable until report issues are resolved.");
    return;
  }
  let parameterValues = {};
  const isQuery = dataset.sourceType === "query" || dataset.source_type === "query";
  if (isQuery && (dataset.parameters || []).length > 0) {
    const collected = await runtimeParameterDialog.collectRuntimeParameters(dataset.id, {
      openingControl: openingControl
        || elements.toolbar.querySelector('[data-command="preview"]'),
      actionLabel: "Preview Report"
    });
    if (collected.cancelled) {
      setStatus("Preview cancelled");
      return;
    }
    parameterValues = collected.values;
  }
  await livePreview.open(dataset.id, parameterValues, {
    openingControl: openingControl
      || elements.toolbar.querySelector('[data-command="preview"]')
  });
}

function primaryRuntimeDataset(template) {
  if (!runtime.sqlDatasetsEnabled) {
    return null;
  }
  const detailIds = new Set(
    (template.bands || [])
      .filter((band) => band.id === "detail" || band.type === "detail")
      .map((band) => getBandDatasetId(band))
      .filter(Boolean)
  );
  if (detailIds.size !== 1) {
    return null;
  }
  return getDatasetById(template, [...detailIds][0]);
}

async function saveCurrentReport() {
  const validation = await validateTemplateSave(state.template);
  if (!validation.canSave) {
    showReportAttention(validation.errors);
    setStatus("Save blocked by structural or security errors.");
    return false;
  }
  if (validation.warnings?.length) {
    const decision = await showSaveWarning(validation.warnings);
    if (decision !== "save") {
      if (decision === "review") {
        showReportAttention(validation.warnings);
      }
      setStatus("Save cancelled");
      return false;
    }
  }
  state.template = normalizeTemplate(await saveTemplate(state.template));
  state.dirty = false;
  createVersion(currentTemplateId(), state.template, "Saved");
  setStatus("Saved");
  return true;
}

async function inspectCurrentReport() {
  try {
    const result = await inspectReopenedTemplate(state.template);
    if (result.issues?.length) {
      showReportAttention(result.issues);
    } else {
      elements.reportAttention.hidden = true;
    }
  } catch (error) {
    showReportAttention([{
      code: "inspection_unavailable",
      message: "Report readiness could not be checked. Editing remains available."
    }]);
  }
}

function showReportAttention(issues = []) {
  const actionable = issues.filter((issue) => issue.severity !== "info");
  const visible = actionable.length ? actionable : issues;
  if (!visible.length) {
    elements.reportAttention.hidden = true;
    return;
  }
  const first = visible[0]?.message || "Review the saved report configuration.";
  const remaining = visible.length - 1;
  elements.reportAttentionMessage.textContent = remaining > 0
    ? `${first} ${remaining} more issue${remaining === 1 ? "" : "s"}.`
    : first;

  elements.reportAttentionDataSources.hidden =
    !runtime.databaseDataSourcesEnabled
    || !visible.some((issue) => (
      issue.dataSourceId || String(issue.code || "").includes("credential")
    ));

  elements.reportAttentionDatasets.hidden =
    !runtime.sqlDatasetsEnabled
    || !visible.some((issue) => (
      issue.datasetId
        || String(issue.code || "").includes("dataset")
        || String(issue.code || "").includes("binding")
    ));

  elements.reportAttention.hidden = false;
}

function showSaveWarning(warnings) {
  elements.saveWarningList.replaceChildren();
  for (const warning of warnings) {
    const item = document.createElement("li");
    item.textContent = warning.message;
    elements.saveWarningList.appendChild(item);
  }
  elements.saveWarningModal.hidden = false;
  elements.saveWarningConfirm.focus();
  return new Promise((resolve) => {
    const finish = (decision) => {
      elements.saveWarningModal.hidden = true;
      elements.saveWarningConfirm.onclick = null;
      elements.saveWarningReview.onclick = null;
      elements.saveWarningCancel.onclick = null;
      resolve(decision);
    };
    elements.saveWarningConfirm.onclick = () => finish("save");
    elements.saveWarningReview.onclick = () => finish("review");
    elements.saveWarningCancel.onclick = () => finish("cancel");
  });
}

async function loadCreatedReport(template) {
  await dataSourceManager.clearRuntimePasswords();
  rotateReportSessionKey();
  state.template = normalizeTemplate(safeTemplateSnapshot(template));
  state.selectedIds = [];
  state.primarySelectedId = null;
  state.activeBandId = getBandById(state.template, "detail")?.id
    || state.template.bands?.[0]?.id
    || "detail";
  state.undoStack = [];
  state.redoStack = [];
  state.collapsedDatasetIds.clear();
  state.selectedDatasetField = null;
  state.hostFields = [];
  let fieldCatalogWarning = "";
  try {
    await refreshHostFieldCatalog();
  } catch (error) {
    fieldCatalogWarning = `Host field catalog unavailable: ${error.message}`;
  }
  state.dirty = true;
  state.statusMessage = fieldCatalogWarning || "New report created.";
  render();
}

function addGroup() {
  recordUndo("Add group bands");
  const groupHeader = addGroupBands(state.template);
  state.activeBandId = groupHeader?.id || state.activeBandId;
  state.selectedIds = [];
  state.primarySelectedId = null;
  markDirty("Group bands added");
}

function applyDataSourceTemplate(template, historyLabel, statusMessage) {
  recordUndo(historyLabel);
  state.template = normalizeTemplate(template);
  ensureActiveBand();
  markDirty(statusMessage);
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
  const affectedBands = state.template.objects
    .filter((object) => selected.has(object.id) && getDatasetFieldBinding(object))
    .map((object) => object.band || object.band_id || "detail");
  const count = state.template.objects.filter((object) => selected.has(object.id)).length;
  state.template.objects = state.template.objects.filter((object) => !selected.has(object.id));
  clearEmptyBandDatasetContexts(state.template, affectedBands);
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
  return `${JSON.stringify(safeTemplateSnapshot(state.template), null, 2)}\n`;
}

function addFieldObject(path, position = null) {
  const originalPath = normalizeFieldPath(path);
  const repeat = activeRepeatForBand(state.activeBandId);
  const binding = repeat ? rowRelativeBinding(originalPath, repeat.data_path) : originalPath;
  if (!binding) {
    setStatus("Binding not found");
    return;
  }
  recordUndo(`Add field ${binding}`);
  const object = createObject("field", state.template);
  object.width = 140;
  object.height = 20;
  setObjectBinding(object, binding);
  if (repeat && binding !== originalPath) {
    object.source_path = originalPath;
    object.properties.source_path = originalPath;
  }
  assignObjectBand(state.template, object, state.activeBandId);
  if (position) {
    object.x = position.x;
    object.y = position.y;
  } else {
    placeObjectOnCanvas(object, state.template, state.canvasSettings, elements.canvasScroller);
    const insertionIndex = state.template.objects.filter((item) => {
      return (item.band || item.band_id || "detail") === band.id && getDatasetFieldBinding(item);
    }).length;
    object.x += (insertionIndex % 6) * 8;
    object.y += (insertionIndex % 6) * 8;
  }
  if (repeat) {
    const band = getBandById(state.template, "detail");
    const rowTop = Number(band?.y) || 0;
    const rowBottom = rowTop + (Number(repeat.row_height) || 22);
    object.y = Math.max(rowTop, Math.min(Number(object.y) || rowTop, rowBottom - object.height));
  }
  clampObjectToBand(state.template, object);
  state.template.objects.push(object);
  selectOnly(object.id);
  markDirty(`Field added: ${binding}`);
}

function selectDatasetFieldButton(button) {
  state.selectedDatasetField = {
    datasetId: button.dataset.datasetId,
    fieldName: button.dataset.fieldName,
    dataType: button.dataset.dataType
  };
  renderFieldsPanel();
}

function insertSelectedDatasetField() {
  if (!state.selectedDatasetField) {
    setStatus("Select a dataset field first");
    return;
  }
  addDatasetFieldObject(state.selectedDatasetField);
}

function addDatasetFieldObject(payload, position = null) {
  const dataset = getDatasetById(state.template, payload.datasetId);
  const field = dataset?.fields?.find((item) => item.name === payload.fieldName);
  const dataType = field?.dataType ?? field?.data_type ?? "unknown";
  const defaults = datasetFieldObjectDefaults(dataType);
  if (!dataset || !field) {
    setStatus("The dataset field no longer exists");
    renderFieldsPanel();
    return;
  }
  if (!defaults) {
    setStatus(`Fields of type ${dataType} cannot be inserted as text`);
    return;
  }
  const band = position ? bandAtPagePosition(position.y) : getBandById(state.template, state.activeBandId);
  if (!band) {
    setStatus("No active band is available for the field");
    return;
  }
  const bandDatasetId = getBandDatasetId(band);
  if (bandDatasetId && bandDatasetId !== dataset.id) {
    setStatus(`Band ${band.name || band.id} already uses dataset ${bandDatasetId}`);
    return;
  }

  recordUndo(`Insert ${dataset.name}.${field.name}`);
  const object = createObject("text", state.template);
  object.width = defaults.width;
  object.height = defaults.height;
  assignObjectBand(state.template, object, band.id);
  setObjectStyleValue(object, "align", defaults.align);
  if (!setDatasetFieldBinding(state.template, object, dataset.id, field.name)) {
    setStatus("The field could not be bound to the selected band");
    return;
  }
  if (position) {
    object.x = position.x;
    object.y = position.y;
  } else {
    placeObjectOnCanvas(object, state.template, state.canvasSettings, elements.canvasScroller);
  }
  clampObjectToBand(state.template, object);
  state.template.objects.push(object);
  state.activeBandId = band.id;
  selectOnly(object.id);
  markDirty(`Inserted ${dataset.name}.${field.name}`);
}

function bandAtPagePosition(y) {
  return (state.template.bands || []).find((band) => {
    const top = Number(band.y) || 0;
    const bottom = top + (Number(band.height) || 0);
    return band.visible !== false && y >= top && y <= bottom;
  }) || getBandById(state.template, state.activeBandId);
}

function renderFieldsPanel() {
  const query = String(elements.fieldSearch.value || "").trim().toLowerCase();
  const allHostPaths = new Set(state.hostFields.map((field) => field.path));
  const hostFields = state.hostFields.filter((field) => fieldMatchesQuery(field, query));
  const sampleFields = getTemplateFields(state.template)
    .filter((field) => !allHostPaths.has(field.path))
    .filter((field) => fieldMatchesQuery(field, query));

  elements.fieldsList.innerHTML = "";
  elements.fieldsList.appendChild(bindingWarningsPanel());

  let visibleDatasetFieldCount = 0;
  if (runtime.sqlDatasetsEnabled) {
    for (const dataset of state.template.datasets || []) {
      const datasetMatches = [dataset.name, dataset.id]
        .some((value) => String(value || "").toLowerCase().includes(query));
      const fields = (dataset.fields || []).filter((field) => {
        if (!query || datasetMatches) {
          return true;
        }
        return [field.name, field.label, field.dataType, field.data_type]
          .some((value) => String(value || "").toLowerCase().includes(query));
      });
      if (query && !datasetMatches && fields.length === 0) {
        continue;
      }
      visibleDatasetFieldCount += fields.length;
      elements.fieldsList.appendChild(datasetFieldGroup(dataset, fields, Boolean(query)));
    }
  }

  if (hostFields.length > 0 || sampleFields.length > 0) {
    elements.fieldsList.appendChild(formulaExamplesPanel());
  }

  appendFieldGroups(hostFields, "Host");
  appendFieldGroups(sampleFields, "Sample");

  const selected = state.selectedDatasetField;
  const selectedStillExists = selected && getDatasetById(state.template, selected.datasetId)?.fields
    ?.some((field) => field.name === selected.fieldName && datasetFieldObjectDefaults(field.dataType ?? field.data_type));
  if (!selectedStillExists) {
    state.selectedDatasetField = null;
  }

  elements.datasetFieldInsert.disabled =
    !runtime.sqlDatasetsEnabled || !state.selectedDatasetField;

  if (
    visibleDatasetFieldCount === 0
    && hostFields.length === 0
    && sampleFields.length === 0
  ) {
    if (query) {
      elements.fieldsList.appendChild(
        fieldsEmptyState("No fields match the search.")
      );
    } else if (
      runtime.sqlDatasetsEnabled
      && (state.template.dataSources || []).length === 0
    ) {
      elements.fieldsList.appendChild(fieldsEmptyState(
        "No data source is configured. Add a MySQL data source before creating datasets.",
        "Open Data Sources",
        "dataSources"
      ));
    } else if (
      runtime.sqlDatasetsEnabled
      && (state.template.datasets || []).length === 0
    ) {
      elements.fieldsList.appendChild(fieldsEmptyState(
        "No datasets are configured. Create a dataset from an approved MySQL view or a read-only SELECT query.",
        "Open Datasets",
        "datasets"
      ));
    } else if (!runtime.sqlDatasetsEnabled) {
      elements.fieldsList.appendChild(
        fieldsEmptyState("No report fields are available.")
      );
    }
  }
}

function appendFieldGroups(fields, prefix) {
  for (const [groupName, groupFields] of Object.entries(groupFieldsByRoot(fields))) {
    const group = document.createElement("section");
    group.className = "field-group";
    const title = document.createElement("div");
    title.className = "field-group-title";
    title.textContent = `${prefix}: ${groupName}`;
    group.appendChild(title);
    for (const field of groupFields) {
      group.appendChild(fieldListItem(field));
    }
    elements.fieldsList.appendChild(group);
  }
}

function availableTemplateFields() {
  const hostPaths = new Set(state.hostFields.map((field) => field.path));
  return [
    ...state.hostFields,
    ...getTemplateFields(state.template).filter((field) => !hostPaths.has(field.path))
  ];
}

function fieldMatchesQuery(field, query) {
  if (!query) {
    return true;
  }
  return [
    field.path,
    field.name,
    field.label,
    field.sample,
    field.dataType,
    field.data_type
  ].some((value) => String(value || "").toLowerCase().includes(query));
}

async function refreshHostFieldCatalog() {
  const templateId = fieldCatalogTemplateId();
  if (!templateId) {
    state.hostFields = [];
    return;
  }

  const fields = await loadFieldCatalog(templateId);
  state.hostFields = fields
    .map(normalizeHostField)
    .filter((field) => Boolean(field.path));
}

function normalizeHostField(field) {
  const path = normalizeFieldPath(field?.name || field?.path || "");
  return {
    ...field,
    name: path,
    path,
    label: String(field?.label || path),
    sample: field?.sample ?? "",
    dataType: field?.dataType ?? field?.data_type ?? "unknown",
    source: "host"
  };
}

function fieldCatalogTemplateId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("template")
    || runtime.templateId
    || state.template?.metadata?.custom?.id
    || "";
}

function datasetFieldGroup(dataset, fields, searchActive) {
  const group = document.createElement("section");
  group.className = "field-group dataset-group";
  const collapsed = !searchActive && state.collapsedDatasetIds.has(dataset.id);
  const header = document.createElement("div");
  header.className = "dataset-group-header";
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "dataset-toggle";
  toggle.dataset.datasetToggle = dataset.id;
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.title = collapsed ? "Expand dataset" : "Collapse dataset";
  toggle.textContent = collapsed ? ">" : "v";
  const title = document.createElement("span");
  title.className = "dataset-title";
  const name = document.createElement("span");
  name.textContent = dataset.name || dataset.id;
  const source = document.createElement("span");
  source.className = "dataset-source-summary";
  const sourceLabel = dataset.sourceType === "query" || dataset.source_type === "query"
    ? "Custom SELECT query"
    : String(dataset.viewName ?? dataset.view_name ?? "Approved view");
  const parameterCount = (dataset.parameters || []).length;
  source.textContent = `${sourceLabel} | ${(dataset.fields || []).length} fields${parameterCount ? ` | ${parameterCount} parameters` : ""}`;
  title.append(name, source);
  title.title = `${dataset.name || dataset.id} (${dataset.id})`;
  header.append(toggle, title);
  group.appendChild(header);
  if (!collapsed) {
    const list = document.createElement("div");
    list.className = "dataset-fields";
    if (fields.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "This dataset has no discovered fields.";
      const manage = document.createElement("button");
      manage.type = "button";
      manage.className = "toolbar-button";
      manage.dataset.fieldsAction = "datasets";
      manage.textContent = "Open Datasets";
      list.append(empty, manage);
    }
    for (const field of fields) {
      list.appendChild(datasetFieldListItem(dataset, field));
    }
    group.appendChild(list);
  }
  return group;
}

function fieldsEmptyState(message, actionLabel = "", action = "") {
  const container = document.createElement("div");
  container.className = "empty-state fields-empty-state";
  const text = document.createElement("div");
  text.textContent = message;
  container.appendChild(text);
  if (actionLabel && action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toolbar-button";
    button.dataset.fieldsAction = action;
    button.textContent = actionLabel;
    container.appendChild(button);
  }
  return container;
}

function datasetFieldListItem(dataset, field) {
  const dataType = String(field.dataType ?? field.data_type ?? "unknown");
  const supported = Boolean(datasetFieldObjectDefaults(dataType));
  const button = document.createElement("button");
  button.type = "button";
  button.className = "dataset-field-item";
  button.dataset.datasetField = "true";
  button.dataset.datasetId = dataset.id;
  button.dataset.fieldName = field.name;
  button.dataset.dataType = dataType;
  button.draggable = supported;
  button.disabled = !supported;
  button.title = supported
    ? `${dataset.name}.${field.name} (${dataType})`
    : `${field.name} cannot be inserted as text (${dataType})`;
  if (state.selectedDatasetField?.datasetId === dataset.id
      && state.selectedDatasetField?.fieldName === field.name) {
    button.classList.add("is-selected");
  }
  const name = document.createElement("span");
  name.className = "dataset-field-name";
  name.textContent = field.label || field.name;
  const type = document.createElement("span");
  type.className = "dataset-field-type";
  type.textContent = dataType;
  button.append(name, type);
  return button;
}

function bindingWarningsPanel() {
  const panel = document.createElement("div");
  const warnings = (state.template.objects || [])
    .map((object) => ({ object, status: datasetFieldBindingStatus(state.template, object) }))
    .filter(({ status }) => !["unbound", "bound"].includes(status.state));
  if (warnings.length === 0) {
    return panel;
  }
  panel.className = "binding-warning-list";
  for (const { object, status } of warnings) {
    const warning = document.createElement("div");
    warning.textContent = `${object.id}: ${status.label}`;
    panel.appendChild(warning);
  }
  return panel;
}

function formulaExamplesPanel() {
  const panel = document.createElement("section");
  panel.className = "field-group formula-examples";
  const title = document.createElement("div");
  title.className = "field-group-title";
  title.textContent = "Formula / Condition Examples";
  const examples = document.createElement("div");
  examples.className = "formula-example-list";
  for (const formula of [
    "concat(result, ' ', unit)",
    "if(flag == 'H', 'HIGH', 'NORMAL')",
    "number(numeric_value, 2)",
    "default(patient.middle_name, '')",
    "numeric_value > 10",
    "group.count > 5"
  ]) {
    const item = document.createElement("code");
    item.textContent = formula;
    examples.appendChild(item);
  }
  panel.append(title, examples);
  return panel;
}

function fieldListItem(field) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "field-list-item";
  button.dataset.fieldPath = field.path;
  button.draggable = true;
  button.title = field.label ? `${field.label}: ${field.path}` : field.path;

  const path = document.createElement("span");
  path.className = "field-list-path";
  path.textContent = field.path;

  const meta = document.createElement("span");
  meta.className = "field-list-meta";
  const label = document.createElement("span");
  label.textContent = field.label || "Field";
  const sample = document.createElement("span");
  sample.textContent = field.sample || sampleValueLabel(getFieldValue(state.template?.data?.sample || {}, field.path));
  meta.append(label, sample);
  button.append(path, meta);
  return button;
}

function groupFieldsByRoot(fields) {
  return fields.reduce((groups, field) => {
    const root = field.path.split(".")[0]?.replace(/\[(?:\d+)?\]/g, "") || "Fields";
    const label = root.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
    groups[label] = groups[label] || [];
    groups[label].push(field);
    return groups;
  }, {});
}

function sampleValueLabel(value) {
  if (value === undefined || value === null) {
    return "";
  }
  return String(value);
}

function canvasDropPosition(event) {
  const page = state.template?.page || {};
  const rect = elements.canvas.getBoundingClientRect();
  const zoom = Number(state.canvasSettings.zoom) || 1;
  const unitScale = unitToPx(1, page.unit);
  return {
    x: Math.round((event.clientX - rect.left) / zoom / unitScale),
    y: Math.round((event.clientY - rect.top) / zoom / unitScale)
  };
}

function showLeftPanel(panelName) {
  for (const tab of elements.toolbox.querySelectorAll("[data-panel-tab]")) {
    const active = tab.dataset.panelTab === panelName;
    tab.classList.toggle("is-active", active);
  }
  for (const panel of elements.toolbox.querySelectorAll("[data-panel]")) {
    const active = panel.dataset.panel === panelName;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  }
  if (panelName === "fields") {
    renderFieldsPanel();
  }
}

function initializeToolboxIcons() {
  for (const item of elements.toolbox.querySelectorAll("[data-icon]")) {
    applyIcon(item, item.dataset.icon);
  }
}

function initializeSampleDataUi() {
  applyIcon(elements.sampleDataOpen, "database");
  applyIcon(elements.sampleDataClose, "close");
  elements.sampleDataOpen.addEventListener("click", openSampleDataModal);
  elements.sampleDataClose.addEventListener("click", closeSampleDataModal);
  elements.sampleDataApply.addEventListener("click", applySampleData);
  elements.sampleDataModal.addEventListener("click", (event) => {
    if (event.target === elements.sampleDataModal) {
      closeSampleDataModal();
    }
  });
}

function openSampleDataModal() {
  elements.sampleDataJson.value = JSON.stringify(state.template?.data?.sample || {}, null, 2);
  elements.sampleDataError.hidden = true;
  elements.sampleDataError.textContent = "";
  elements.sampleDataModal.hidden = false;
  elements.sampleDataJson.focus();
}

function closeSampleDataModal() {
  elements.sampleDataModal.hidden = true;
}

function applySampleData() {
  let sample;
  try {
    sample = JSON.parse(elements.sampleDataJson.value || "{}");
  } catch (error) {
    elements.sampleDataError.textContent = `Invalid JSON: ${error.message}`;
    elements.sampleDataError.hidden = false;
    setStatus("Invalid JSON");
    return;
  }
  if (!sample || typeof sample !== "object" || Array.isArray(sample)) {
    elements.sampleDataError.textContent = "Sample data must be a JSON object.";
    elements.sampleDataError.hidden = false;
    setStatus("Invalid JSON");
    return;
  }
  recordUndo("Edit sample data");
  state.template.data = {
    ...(state.template.data || {}),
    sample,
    fields: inferFieldsFromSample(sample)
  };
  closeSampleDataModal();
  markDirty("Sample data updated");
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
  renderFieldsPanel();
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
  return state.template ? safeTemplateSnapshot(state.template) : null;
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
  void dataSourceManager.clearRuntimePasswords();
  rotateReportSessionKey();
  state.template = normalizeTemplate(safeTemplateSnapshot(snapshot));
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
  const repeat = activeRepeatForBand("detail");
  const repeatLabel = repeat?.enabled
    ? ` | Repeat: On | Data: ${repeat.data_path || "missing"} | Rows: ${repeat.preview_rows || 10}`
    : " | Repeat: Off";
  return `Band: ${bandLabel(state.activeBandId)} | Grid: ${settings.grid_size}px | Zoom: ${Math.round(settings.zoom * 100)}% | Snap: ${settings.snap_to_grid ? "On" : "Off"}${repeatLabel}`;
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

function activeRepeatForBand(bandId) {
  const band = getBandById(state.template, bandId);
  if (band?.id === "detail" && band.repeat?.enabled) {
    return band.repeat;
  }
  if (["group_header", "group_footer"].includes(band?.type)) {
    const detail = getBandById(state.template, "detail");
    const dataPath = band.group?.data_path || detail?.repeat?.data_path || "";
    return dataPath ? { enabled: true, data_path: dataPath } : null;
  }
  return null;
}

function rowRelativeBinding(path, repeatDataPath) {
  return relativeFieldPathForCollection(path, repeatDataPath);
}

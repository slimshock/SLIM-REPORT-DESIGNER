import {
  buildNewReport,
  createMysqlDataSource,
  createQueryDataset,
  createViewDataset,
  listReportingViews,
  testMysqlDataSource,
  testSavedMysqlDataSource,
  validateDatasetQuery
} from "./api.js";
import { createDefaultTemplate, normalizeTemplate, paperDimensions } from "./objects.js";

export function createNewReportWizard({
  root,
  getTemplate,
  isDirty,
  onSave,
  onCreate,
  onStatus = () => {}
}) {
  const ui = {
    close: root.querySelector("#new-report-close"),
    content: root.querySelector("#new-report-content")
  };
  let draft = null;
  let trigger = null;

  ui.close.addEventListener("click", cancel);
  root.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-wizard-action]");
    if (button) {
      void handleAction(button.dataset.wizardAction);
    }
  });
  root.addEventListener("change", (event) => {
    if (!draft || !event.target.matches("[data-wizard-rerender]")) {
      return;
    }
    captureStep();
    render();
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      showMessage("Use Cancel to close the wizard without changing the current report.");
    }
  });

  return {
    open(openTrigger = null) {
      trigger = openTrigger;
      root.hidden = false;
      if (isDirty()) {
        renderUnsavedConfirmation();
      } else {
        startDraft();
      }
    },
    isOpen: () => !root.hidden
  };

  function startDraft() {
    draft = createWizardDraft(getTemplate());
    render();
  }

  function cancel() {
    clearSecrets();
    draft = null;
    root.hidden = true;
    ui.content.innerHTML = "";
    trigger?.focus?.();
  }

  function renderUnsavedConfirmation() {
    ui.content.innerHTML = `
      <div class="wizard-body">
        <h3>Create a new report?</h3>
        <div class="wizard-message is-warning" role="alert">
          The current report has unsaved changes.
        </div>
        <p>The active report will remain unchanged until a new report is created successfully.</p>
      </div>
      <footer class="wizard-actions">
        <button class="toolbar-button" type="button" data-wizard-action="cancel">Cancel</button>
        <span class="button-spacer"></span>
        <button class="toolbar-button" type="button" data-wizard-action="discard">Continue Without Saving</button>
        <button class="toolbar-button primary" type="button" data-wizard-action="saveContinue">Save and Continue</button>
      </footer>`;
    ui.content.querySelector('[data-wizard-action="cancel"]')?.focus();
  }

  async function handleAction(action) {
    try {
      if (action === "cancel") {
        cancel();
      } else if (action === "discard") {
        startDraft();
      } else if (action === "saveContinue") {
        await onSave();
        startDraft();
      } else if (action === "back") {
        captureStep();
        draft.step = Math.max(0, draft.step - 1);
        draft.message = "";
        render();
      } else if (action === "next") {
        await nextStep();
      } else if (action === "loadViews") {
        captureStep();
        await prepareSource();
        const response = await listReportingViews(draft.template, draft.sourceId);
        draft.views = response.views || [];
        draft.message = `${draft.views.length} approved views loaded.`;
        render();
      } else if (action === "testConnection") {
        captureStep();
        await testConnection();
      } else if (action === "validateQuery") {
        captureStep();
        await validateQuery();
      } else if (action === "discoverFields") {
        captureStep();
        await prepareDataset(true);
        draft.message = `${draft.fields.length} fields discovered.`;
        render();
      } else if (action === "selectAll") {
        captureStep();
        draft.selectedFields = new Set(
          draft.fields.filter(isTextField).map((field) => field.name)
        );
        render();
      } else if (action === "clearFields") {
        captureStep();
        draft.selectedFields.clear();
        render();
      } else if (action === "create") {
        await createReport();
      }
    } catch (error) {
      showMessage(error.message || "The wizard action failed.", true);
    }
  }

  async function nextStep() {
    captureStep();
    const step = steps()[draft.step];
    validateStep(step.id);
    if (step.id === "source") {
      await prepareSource();
    } else if (step.id === "dataset") {
      await prepareDataset(false);
    }
    draft.step = Math.min(steps().length - 1, draft.step + 1);
    draft.message = "";
    render();
  }

  function validateStep(stepId) {
    if (stepId === "report" && !draft.reportName.trim()) {
      throw new Error("Report Name is required.");
    }
    if (stepId === "page") {
      const dimensions = pageDimensions(draft);
      if (dimensions.width <= 0 || dimensions.height <= 0) {
        throw new Error("Page width and height must be positive.");
      }
      if (draft.margins.left + draft.margins.right >= dimensions.width
          || draft.margins.top + draft.margins.bottom >= dimensions.height) {
        throw new Error("Page margins leave no printable report area.");
      }
    }
    if (stepId === "source" && draft.sourceMode === "existing" && !draft.existingSourceId) {
      throw new Error("Select an existing MySQL data source.");
    }
    if (stepId === "dataset") {
      if (!draft.datasetName.trim()) {
        throw new Error("Dataset Name is required.");
      }
      if (draft.datasetType === "view" && !draft.viewName) {
        throw new Error("Select an approved reporting view.");
      }
      if (draft.datasetType === "query" && !draft.query.trim()) {
        throw new Error("Enter one read-only SELECT query.");
      }
    }
    if (stepId === "layout" && draft.layoutType === "tabular") {
      if (draft.selectedFields.size === 0) {
        throw new Error("Tabular layout requires at least one selected field.");
      }
      if (isNarrowLayout(draft) && !draft.allowNarrowColumns) {
        throw new Error("Confirm Create Anyway, switch to landscape, or reduce selected fields.");
      }
    }
  }

  async function prepareSource() {
    const fingerprint = sourceFingerprint(draft);
    if (draft.sourceFingerprint === fingerprint && draft.sourceId) {
      return;
    }
    const template = createDefaultTemplate();
    if (draft.sourceMode === "existing") {
      const source = (getTemplate().dataSources || [])
        .find((item) => item.id === draft.existingSourceId && item.type === "mysql");
      if (!source) {
        throw new Error("The selected MySQL data source is no longer available.");
      }
      const safeSource = structuredClone(source);
      if (safeSource.connection) {
        delete safeSource.connection.password;
      }
      template.dataSources = [safeSource];
      draft.template = normalizeTemplate(template);
      draft.sourceId = safeSource.id;
    } else {
      const values = newSourceValues(draft);
      const response = await createMysqlDataSource(template, values);
      draft.template = normalizeTemplate(response.template);
      draft.sourceId = response.dataSource?.id || draft.template.dataSources?.[0]?.id || "";
      if (values.credentialMode === "runtimePassword" && values.password) {
        draft.template.dataSources[0].connection.password = values.password;
      }
    }
    draft.sourceFingerprint = fingerprint;
    invalidateDataset();
  }

  async function testConnection() {
    if (draft.sourceMode === "new") {
      const response = await testMysqlDataSource(newSourceValues(draft));
      draft.message = response.message || "Connection succeeded.";
    } else {
      await prepareSource();
      const response = await testSavedMysqlDataSource(draft.template, draft.sourceId);
      draft.message = response.message || "Connection succeeded.";
    }
    render();
  }

  async function validateQuery() {
    await prepareSource();
    const response = await validateDatasetQuery(draft.template, {
      query: draft.query,
      parameters: draft.parameters
    });
    const existing = new Map(draft.parameters.map((item) => [item.name.toLowerCase(), item]));
    draft.parameters = (response.parameters || []).map((name) => ({
      name,
      dataType: existing.get(name.toLowerCase())?.dataType || "string",
      required: existing.get(name.toLowerCase())?.required || false,
      default: existing.get(name.toLowerCase())?.default ?? null,
      label: existing.get(name.toLowerCase())?.label || friendlyLabel(name)
    }));
    draft.queryFingerprint = queryFingerprint(draft);
    draft.message = draft.parameters.length
      ? `${draft.parameters.length} named parameters detected. Configure temporary values before discovery.`
      : "Query is a valid read-only SELECT. No query parameters detected.";
    render();
  }

  async function prepareDataset(force = false) {
    await prepareSource();
    const fingerprint = datasetFingerprint(draft);
    if (!force && draft.datasetFingerprint === fingerprint && draft.fields.length) {
      return;
    }
    let response;
    draft.template.datasets = [];
    if (draft.datasetType === "view") {
      response = await createViewDataset(draft.template, {
        name: draft.datasetName,
        dataSourceId: draft.sourceId,
        viewName: draft.viewName
      });
    } else {
      if (draft.queryFingerprint !== queryFingerprint(draft)) {
        await validateQuery();
        throw new Error("Review query parameters, then discover fields again.");
      }
      response = await createQueryDataset(draft.template, {
        name: draft.datasetName,
        dataSourceId: draft.sourceId,
        query: draft.query,
        parameters: draft.parameters,
        parameterValues: draft.temporaryValues
      });
    }
    draft.template = normalizeTemplate(response.template);
    const dataset = draft.template.datasets?.[0];
    if (!dataset || !(dataset.fields || []).length) {
      throw new Error("Field discovery returned no fields.");
    }
    draft.datasetId = dataset.id;
    draft.fields = dataset.fields || [];
    draft.selectedFields = new Set(draft.fields.filter(isTextField).map((field) => field.name));
    draft.labels = Object.fromEntries(
      draft.fields.map((field) => [field.name, field.label || friendlyLabel(field.name)])
    );
    draft.datasetFingerprint = fingerprint;
  }

  function invalidateDataset() {
    draft.template.datasets = [];
    draft.datasetId = "";
    draft.datasetFingerprint = "";
    draft.fields = [];
    draft.selectedFields.clear();
    draft.labels = {};
  }

  async function createReport() {
    captureStep();
    validateStep("layout");
    const configuration = buildConfiguration(draft);
    const response = await buildNewReport(configuration);
    if (!response.template) {
      throw new Error("The server did not return a generated report template.");
    }
    const created = normalizeTemplate(response.template);
    await onCreate(created);
    clearSecrets();
    draft = null;
    root.hidden = true;
    ui.content.innerHTML = "";
    onStatus(response.message || "New report created.");
  }

  function render() {
    const allSteps = steps();
    if (draft.step >= allSteps.length) {
      draft.step = allSteps.length - 1;
    }
    const current = allSteps[draft.step];
    ui.content.innerHTML = `
      ${progressMarkup(allSteps, draft.step)}
      <div class="wizard-body">
        ${draft.message ? `<div class="wizard-message" role="status">${escapeHtml(draft.message)}</div>` : ""}
        <div id="wizard-error" class="wizard-message is-error" role="alert" hidden></div>
        ${stepMarkup(current.id)}
      </div>
      ${footerMarkup(current.id)}`;
    ui.content.querySelector("input:not([type=hidden]), select, textarea, button")?.focus();
  }

  function showMessage(message, error = false) {
    const target = ui.content.querySelector("#wizard-error");
    if (!target) {
      draft.message = message;
      render();
      return;
    }
    target.textContent = message;
    target.classList.toggle("is-error", error);
    target.hidden = false;
    target.focus?.();
  }

  function steps() {
    return draft.mode === "blank"
      ? [step("report", "Report"), step("page", "Page"), step("layout", "Layout"), step("review", "Review")]
      : [
          step("report", "Report"),
          step("page", "Page"),
          step("source", "Data Source"),
          step("dataset", "Dataset"),
          step("fields", "Fields"),
          step("layout", "Layout"),
          step("review", "Review")
        ];
  }

  function stepMarkup(id) {
    if (id === "report") return reportStep(draft);
    if (id === "page") return pageStep(draft);
    if (id === "source") return sourceStep(draft, getTemplate());
    if (id === "dataset") return datasetStep(draft);
    if (id === "fields") return fieldsStep(draft);
    if (id === "layout") return layoutStep(draft);
    return reviewStep(draft);
  }

  function footerMarkup(id) {
    const review = id === "review";
    return `<footer class="wizard-actions">
      <button class="toolbar-button" type="button" data-wizard-action="cancel">Cancel</button>
      <span class="button-spacer"></span>
      <button class="toolbar-button" type="button" data-wizard-action="back" ${draft.step === 0 ? "disabled" : ""}>Back</button>
      ${review
        ? '<button class="toolbar-button primary" type="button" data-wizard-action="create">Create Report</button>'
        : '<button class="toolbar-button primary" type="button" data-wizard-action="next">Next</button>'}
    </footer>`;
  }

  function captureStep() {
    if (!draft) return;
    const form = ui.content.querySelector("[data-wizard-form]");
    if (!form) return;
    const values = new FormData(form);
    const id = steps()[draft.step]?.id;
    if (id === "report") {
      draft.reportName = String(values.get("reportName") || "");
      draft.description = String(values.get("description") || "");
      draft.mode = String(values.get("mode") || "blank");
    } else if (id === "page") {
      draft.pageSize = String(values.get("pageSize") || "A4");
      draft.orientation = String(values.get("orientation") || "portrait");
      draft.customWidth = numberValue(values.get("customWidth"), 595);
      draft.customHeight = numberValue(values.get("customHeight"), 842);
      for (const side of ["top", "right", "bottom", "left"]) {
        draft.margins[side] = numberValue(values.get(`margin_${side}`), 24);
      }
    } else if (id === "source") {
      draft.sourceMode = String(values.get("sourceMode") || "existing");
      draft.existingSourceId = String(values.get("existingSourceId") || "");
      for (const key of Object.keys(draft.newSource)) {
        if (values.has(key)) draft.newSource[key] = String(values.get(key) || "");
      }
    } else if (id === "dataset") {
      draft.datasetType = String(values.get("datasetType") || "view");
      draft.datasetName = String(values.get("datasetName") || "Main Dataset");
      draft.viewName = String(values.get("viewName") || "");
      draft.query = String(values.get("query") || "");
      draft.parameters = draft.parameters.map((parameter, index) => ({
        ...parameter,
        dataType: String(values.get(`parameterType_${index}`) || parameter.dataType),
        required: values.get(`parameterRequired_${index}`) === "on",
        default: parseOptionalValue(values.get(`parameterDefault_${index}`)),
        label: String(values.get(`parameterLabel_${index}`) || parameter.label)
      }));
      draft.temporaryValues = Object.fromEntries(
        draft.parameters.map((parameter, index) => [
          parameter.name,
          String(values.get(`temporaryValue_${index}`) || "")
        ])
      );
    } else if (id === "fields") {
      draft.selectedFields = new Set(
        draft.fields
          .filter((_, index) => values.get(`selected_${index}`) === "on")
          .map((field) => field.name)
      );
      draft.labels = Object.fromEntries(
        draft.fields.map((field, index) => [
          field.name,
          String(values.get(`label_${index}`) || friendlyLabel(field.name))
        ])
      );
    } else if (id === "layout") {
      draft.layoutType = String(values.get("layoutType") || "blank");
      draft.includeTitle = values.get("includeTitle") === "on";
      draft.includeColumnHeaders = values.get("includeColumnHeaders") === "on";
      draft.allowNarrowColumns = values.get("allowNarrowColumns") === "on";
    }
  }

  function clearSecrets() {
    if (draft?.newSource) draft.newSource.password = "";
    if (draft) draft.temporaryValues = {};
    for (const input of root.querySelectorAll('input[type="password"]')) input.value = "";
  }
}

export function createWizardDraft(template) {
  const mysqlSources = (template?.dataSources || []).filter((item) => item.type === "mysql");
  return {
    step: 0,
    mode: "blank",
    reportName: "Untitled Report",
    description: "",
    pageSize: "A4",
    orientation: "portrait",
    customWidth: 595,
    customHeight: 842,
    margins: { top: 24, right: 24, bottom: 24, left: 24 },
    sourceMode: mysqlSources.length ? "existing" : "new",
    existingSourceId: mysqlSources[0]?.id || "",
    newSource: {
      name: "Main MySQL", host: "localhost", port: "3306", database: "",
      username: "", credentialMode: "passwordRef", password: "", passwordRef: "",
      charset: "utf8mb4", connectTimeout: "10", queryTimeout: "30"
    },
    sourceId: "",
    sourceFingerprint: "",
    template: createDefaultTemplate(),
    datasetType: "view",
    datasetName: "Main Dataset",
    datasetId: "",
    viewName: "",
    views: [],
    query: "SELECT ",
    queryFingerprint: "",
    parameters: [],
    temporaryValues: {},
    datasetFingerprint: "",
    fields: [],
    selectedFields: new Set(),
    labels: {},
    layoutType: "blank",
    includeTitle: true,
    includeColumnHeaders: true,
    allowNarrowColumns: false,
    message: ""
  };
}

export function friendlyLabel(value) {
  const acronyms = new Map([["id", "ID"], ["dob", "DOB"], ["pid", "PID"], ["hgb", "HGB"], ["wbc", "WBC"]]);
  return String(value || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((word) => acronyms.get(word.toLowerCase()) || `${word[0].toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

export function buildConfiguration(draft) {
  const source = draft.mode === "mysql" ? structuredClone(draft.template.dataSources?.[0]) : null;
  if (source?.connection) delete source.connection.password;
  const dataset = draft.mode === "mysql" ? structuredClone(draft.template.datasets?.[0]) : null;
  const selectedFields = draft.fields
    .filter((field) => draft.selectedFields.has(field.name))
    .map((field, index) => ({ field: field.name, label: draft.labels[field.name], order: index }));
  const dimensions = pageDimensions(draft);
  return {
    report: { name: draft.reportName.trim(), description: draft.description.trim() || null },
    page: {
      size: draft.pageSize,
      orientation: draft.orientation,
      width: dimensions.width,
      height: dimensions.height,
      marginTop: draft.margins.top,
      marginRight: draft.margins.right,
      marginBottom: draft.margins.bottom,
      marginLeft: draft.margins.left
    },
    dataSource: source,
    dataset,
    layout: {
      type: draft.layoutType,
      includeTitle: draft.includeTitle,
      includeColumnHeaders: draft.includeColumnHeaders,
      allowNarrowColumns: draft.allowNarrowColumns,
      selectedFields
    }
  };
}

function reportStep(draft) {
  return `<form data-wizard-form><h3>Report Information</h3><div class="wizard-grid">
    ${field("Report Name", "reportName", draft.reportName, "text", true)}
    ${field("Description", "description", draft.description, "text")}
    <fieldset class="wizard-field is-wide"><legend>Start With</legend><div class="wizard-choice-list">
      ${choice("mode", "blank", draft.mode, "Blank Report", "Create a report without a data source or dataset.", true)}
      ${choice("mode", "mysql", draft.mode, "MySQL Report", "Use an approved reporting view or validated read-only SELECT query.", true)}
    </div></fieldset></div></form>`;
}

function pageStep(draft) {
  const custom = draft.pageSize === "Custom";
  const dimensions = pageDimensions(draft);
  return `<form data-wizard-form><h3>Page Configuration</h3><div class="wizard-grid">
    ${selectField("Page Size", "pageSize", ["A4", "Letter", "Legal", "Custom"], draft.pageSize, true)}
    ${selectField("Orientation", "orientation", ["portrait", "landscape"], draft.orientation, true)}
    ${custom ? field("Custom Width", "customWidth", draft.customWidth, "number", true) : ""}
    ${custom ? field("Custom Height", "customHeight", draft.customHeight, "number", true) : ""}
    ${["top", "right", "bottom", "left"].map((side) => field(`${capitalize(side)} Margin`, `margin_${side}`, draft.margins[side], "number", true)).join("")}
    <div><div class="wizard-page-preview" style="aspect-ratio:${dimensions.width}/${dimensions.height};height:auto"></div><small>${dimensions.width} x ${dimensions.height} px</small></div>
  </div></form>`;
}

function sourceStep(draft, activeTemplate) {
  const sources = (activeTemplate.dataSources || []).filter((item) => item.type === "mysql");
  const existingOptions = sources.map((source) => `<option value="${escapeAttr(source.id)}" ${source.id === draft.existingSourceId ? "selected" : ""}>${escapeHtml(source.name || source.id)}</option>`).join("");
  return `<form data-wizard-form><h3>MySQL Data Source</h3>
    <div class="wizard-choice-list">
      ${choice("sourceMode", "existing", draft.sourceMode, "Use Existing", "Copy a safe MySQL definition from the current report.", true, !sources.length)}
      ${choice("sourceMode", "new", draft.sourceMode, "Create New", "Configure a new MySQL data source in the temporary draft.", true)}
    </div>
    <div class="wizard-grid" style="margin-top:12px">
      ${draft.sourceMode === "existing" ? `<label class="wizard-field is-wide"><span>Existing Data Source</span><select name="existingSourceId">${existingOptions}</select></label>` : newSourceFields(draft)}
    </div>
    <div style="margin-top:12px"><button class="toolbar-button" type="button" data-wizard-action="testConnection">Test Connection</button></div>
  </form>`;
}

function newSourceFields(draft) {
  const source = draft.newSource;
  return [
    field("Data Source Name", "name", source.name, "text", true),
    field("Host", "host", source.host, "text", true),
    field("Port", "port", source.port, "number", true),
    field("Database", "database", source.database, "text", true),
    field("Username", "username", source.username, "text", true),
    selectField("Credential Method", "credentialMode", ["passwordRef", "runtimePassword", "none"], source.credentialMode, true),
    source.credentialMode === "passwordRef" ? field("Environment Password Reference", "passwordRef", source.passwordRef, "text", true) : "",
    source.credentialMode === "runtimePassword" ? field("Runtime Password", "password", source.password, "password", true) : "",
    field("Charset", "charset", source.charset, "text", true),
    field("Connect Timeout", "connectTimeout", source.connectTimeout, "number", true),
    field("Query Timeout", "queryTimeout", source.queryTimeout, "number", true)
  ].join("");
}

function datasetStep(draft) {
  const query = draft.datasetType === "query";
  const views = draft.views.map((view) => `<option value="${escapeAttr(view.viewName)}" ${view.viewName === draft.viewName ? "selected" : ""}>${escapeHtml(view.displayName || view.viewName)}</option>`).join("");
  return `<form data-wizard-form><h3>Dataset Configuration</h3>
    <div class="wizard-choice-list">
      ${choice("datasetType", "view", draft.datasetType, "Reporting View", "Use an approved MySQL reporting view.", true)}
      ${choice("datasetType", "query", draft.datasetType, "Custom SELECT Query", "Use one validated read-only SELECT query.", true)}
    </div>
    <div class="wizard-grid" style="margin-top:12px">
      ${field("Dataset Name", "datasetName", draft.datasetName, "text", true)}
      ${!query ? `<label class="wizard-field"><span>Approved View</span><select name="viewName"><option value="">Select view</option>${views}</select></label>` : ""}
      ${!query ? '<div class="is-wide"><button class="toolbar-button" type="button" data-wizard-action="loadViews">Load Approved Views</button> <button class="toolbar-button" type="button" data-wizard-action="discoverFields">Inspect Fields</button></div>' : ""}
      ${query ? `<label class="wizard-field is-wide"><span>SQL Query</span><textarea name="query" spellcheck="false">${escapeHtml(draft.query)}</textarea></label>` : ""}
      ${query ? '<div class="is-wide"><button class="toolbar-button" type="button" data-wizard-action="validateQuery">Validate Query</button> <button class="toolbar-button" type="button" data-wizard-action="discoverFields">Discover Fields</button></div>' : ""}
    </div>
    ${query ? parameterTable(draft) : ""}
  </form>`;
}

function parameterTable(draft) {
  if (!draft.parameters.length) return "<p>No query parameters detected.</p>";
  return `<h4>Query Parameters</h4><div style="overflow:auto"><table class="wizard-field-table"><thead><tr><th>Name</th><th>Type</th><th>Required</th><th>Default</th><th>Label</th><th>Temporary Discovery Value</th></tr></thead><tbody>
    ${draft.parameters.map((parameter, index) => `<tr><td>${escapeHtml(parameter.name)}</td><td>${inlineSelect(`parameterType_${index}`, ["string", "integer", "decimal", "boolean", "date", "time", "datetime"], parameter.dataType)}</td><td><input name="parameterRequired_${index}" type="checkbox" ${parameter.required ? "checked" : ""}></td><td><input name="parameterDefault_${index}" value="${escapeAttr(parameter.default ?? "")}"></td><td><input name="parameterLabel_${index}" value="${escapeAttr(parameter.label || "")}"></td><td><input name="temporaryValue_${index}" value="${escapeAttr(draft.temporaryValues[parameter.name] || "")}"></td></tr>`).join("")}
    </tbody></table></div><p class="panel-help">Temporary values are used only for field discovery and are never stored in the report.</p>`;
}

function fieldsStep(draft) {
  return `<form data-wizard-form><h3>Select Starting Fields</h3>
    <div style="margin-bottom:8px"><button class="toolbar-button" type="button" data-wizard-action="selectAll">Select All</button> <button class="toolbar-button" type="button" data-wizard-action="clearFields">Clear All</button></div>
    <div style="overflow:auto"><table class="wizard-field-table"><thead><tr><th>Use</th><th>Field</th><th>Type</th><th>Column Label</th></tr></thead><tbody>
      ${draft.fields.map((field, index) => `<tr><td><input name="selected_${index}" type="checkbox" ${draft.selectedFields.has(field.name) ? "checked" : ""} ${isTextField(field) ? "" : "disabled"}></td><td>${escapeHtml(field.name)}</td><td>${escapeHtml(field.dataType || field.data_type || "unknown")}</td><td><input name="label_${index}" type="text" value="${escapeAttr(draft.labels[field.name] || friendlyLabel(field.name))}"></td></tr>`).join("")}
    </tbody></table></div><p class="panel-help">All discovered fields remain in the dataset. Selection controls only the initial canvas layout.</p>
  </form>`;
}

function layoutStep(draft) {
  const narrow = isNarrowLayout(draft);
  return `<form data-wizard-form><h3>Starting Layout</h3><div class="wizard-choice-list">
    ${choice("layoutType", "blank", draft.layoutType, "Blank", "Keep the configured dataset and place no objects.", true)}
    ${draft.mode === "mysql" ? choice("layoutType", "tabular", draft.layoutType, "Tabular", "Generate static headers and dataset-bound Detail fields.", true) : ""}
    </div>
    ${draft.layoutType === "tabular" ? `<div style="margin-top:12px"><label><input name="includeTitle" type="checkbox" ${draft.includeTitle ? "checked" : ""}> Include Report Title</label><br><label><input name="includeColumnHeaders" type="checkbox" ${draft.includeColumnHeaders ? "checked" : ""}> Include Column Headers</label></div>` : ""}
    ${narrow ? `<div class="wizard-message is-warning" role="alert">${draft.selectedFields.size} selected fields may not fit readably on ${escapeHtml(draft.pageSize)} ${escapeHtml(draft.orientation)}.<br><label><input name="allowNarrowColumns" type="checkbox" ${draft.allowNarrowColumns ? "checked" : ""}> Create Anyway</label></div>` : ""}
  </form>`;
}

function reviewStep(draft) {
  const source = draft.template.dataSources?.[0];
  const dataset = draft.template.datasets?.[0];
  return `<div><h3>Review</h3><div class="wizard-review">
    ${reviewSection("Report", [["Name", draft.reportName], ["Page", `${draft.pageSize} ${capitalize(draft.orientation)}`], ["Layout", capitalize(draft.layoutType)]])}
    ${draft.mode === "mysql" ? reviewSection("Data Source", [["Name", source?.name || ""], ["Host", source?.connection?.host || ""], ["Database", source?.connection?.database || ""], ["Username", source?.connection?.username || ""], ["Credential", source?.connection?.passwordRef ? "Environment reference configured" : "No stored credential"]]) : ""}
    ${draft.mode === "mysql" ? reviewSection("Dataset", [["Name", dataset?.name || ""], ["Type", dataset?.sourceType === "query" ? "Custom SELECT query" : "Reporting View"], ["Fields discovered", String(draft.fields.length)], ["Fields selected", String(draft.selectedFields.size)], ["Parameters", String(dataset?.parameters?.length || 0)]]) : ""}
    ${reviewSection("Generated Layout", [["Page Header", draft.layoutType === "tabular" ? "Configured" : "Empty"], ["Detail fields", draft.layoutType === "tabular" ? String(draft.selectedFields.size) : "0"], ["Live rows", "Not executed"]])}
  </div></div>`;
}

function progressMarkup(steps, current) {
  return `<nav class="wizard-progress" aria-label="New report progress">${steps.map((item, index) => `<span class="wizard-progress-step ${index === current ? "is-current" : ""} ${index < current ? "is-complete" : ""}" ${index === current ? 'aria-current="step"' : ""}>${index + 1}. ${escapeHtml(item.label)}</span>`).join("")}</nav>`;
}

function reviewSection(title, entries) {
  return `<section><h4>${escapeHtml(title)}</h4><dl>${entries.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl></section>`;
}

function field(label, name, value, type = "text", rerender = false) {
  return `<label class="wizard-field"><span>${escapeHtml(label)}</span><input name="${escapeAttr(name)}" type="${type}" value="${escapeAttr(value)}" ${rerender && ["radio", "checkbox"].includes(type) ? "data-wizard-rerender" : ""}></label>`;
}

function selectField(label, name, options, current, rerender = false) {
  return `<label class="wizard-field"><span>${escapeHtml(label)}</span><select name="${escapeAttr(name)}" ${rerender ? "data-wizard-rerender" : ""}>${options.map((value) => `<option value="${escapeAttr(value)}" ${value === current ? "selected" : ""}>${escapeHtml(capitalize(value))}</option>`).join("")}</select></label>`;
}

function inlineSelect(name, options, current) {
  return `<select name="${escapeAttr(name)}">${options.map((value) => `<option value="${value}" ${value === current ? "selected" : ""}>${value}</option>`).join("")}</select>`;
}

function choice(name, value, current, title, description, rerender = false, disabled = false) {
  return `<label class="wizard-choice"><input name="${name}" type="radio" value="${value}" ${value === current ? "checked" : ""} ${rerender ? "data-wizard-rerender" : ""} ${disabled ? "disabled" : ""}><span><strong>${escapeHtml(title)}</strong><span>${escapeHtml(description)}</span></span></label>`;
}

function newSourceValues(draft) {
  const source = draft.newSource;
  return {
    name: source.name,
    host: source.host,
    port: Number(source.port),
    database: source.database,
    username: source.username,
    credentialMode: source.credentialMode,
    password: source.credentialMode === "runtimePassword" ? source.password : null,
    passwordRef: source.credentialMode === "passwordRef" ? source.passwordRef : null,
    charset: source.charset,
    connectTimeout: Number(source.connectTimeout),
    queryTimeout: Number(source.queryTimeout)
  };
}

function pageDimensions(draft) {
  if (draft.pageSize === "Custom") {
    let width = Number(draft.customWidth) || 0;
    let height = Number(draft.customHeight) || 0;
    if (draft.orientation === "landscape" && width < height) [width, height] = [height, width];
    if (draft.orientation === "portrait" && width > height) [width, height] = [height, width];
    return { width, height };
  }
  return paperDimensions(draft.pageSize, "px", draft.orientation);
}

function isNarrowLayout(draft) {
  if (draft.layoutType !== "tabular" || !draft.selectedFields.size) return false;
  const dimensions = pageDimensions(draft);
  const printable = dimensions.width - draft.margins.left - draft.margins.right;
  return printable / draft.selectedFields.size < 48;
}

function sourceFingerprint(draft) {
  return JSON.stringify(draft.sourceMode === "existing" ? ["existing", draft.existingSourceId] : ["new", { ...draft.newSource, password: draft.newSource.password ? "present" : "" }]);
}

function datasetFingerprint(draft) {
  return JSON.stringify([draft.sourceFingerprint, draft.datasetType, draft.datasetName, draft.viewName, draft.query, draft.parameters, draft.temporaryValues]);
}

function queryFingerprint(draft) {
  return JSON.stringify([draft.query, draft.parameters.map(({ name, dataType, required, default: defaultValue, label }) => ({ name, dataType, required, default: defaultValue, label }))]);
}

function isTextField(field) {
  return !["binary", "unknown"].includes(String(field.dataType || field.data_type || "unknown").toLowerCase());
}

function parseOptionalValue(value) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  try { return JSON.parse(text); } catch { return text; }
}

function numberValue(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function step(id, label) { return { id, label }; }
function capitalize(value) { const text = String(value || ""); return `${text[0]?.toUpperCase() || ""}${text.slice(1)}`; }
function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;"); }
function escapeAttr(value) { return escapeHtml(value); }

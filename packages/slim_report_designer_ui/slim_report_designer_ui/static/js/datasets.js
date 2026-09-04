import {
  applyExistingDatasetFields,
  checkDatasetFreshness,
  createQueryDataset,
  createViewDataset,
  deleteDataset,
  discoverDatasetQuery,
  getDataset,
  inspectReportingView,
  listDatasets,
  listReportingViews,
  refreshViewDatasetFields,
  updateQueryDataset,
  updateViewDataset,
  validateDatasetQuery
} from "./api.js";
import { applyIcon } from "./icons.js";

const PARAMETER_TYPES = Object.freeze([
  "string", "integer", "float", "decimal", "boolean", "date", "time", "datetime"
]);

export function parameterLabel(name) {
  return String(name || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.toUpperCase() === "ID"
      ? "ID"
      : `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export function reconcileDetectedParameters(parameters, detected) {
  const existing = new Map(parameters.map((item) => [String(item.name).toLowerCase(), item]));
  return detected.map((name) => {
    const current = existing.get(name.toLowerCase());
    return current ? { ...current, name } : {
      name,
      dataType: "string",
      required: true,
      label: parameterLabel(name)
    };
  });
}

export function queryConfigurationFingerprint(query, parameters) {
  return JSON.stringify({
    query: String(query || ""),
    parameters: parameters.map((item) => ({
      name: item.name,
      dataType: item.dataType,
      required: Boolean(item.required),
      default: item.default ?? null,
      label: item.label || ""
    }))
  });
}

export function createDatasetManager({
  root,
  getTemplate,
  onTemplateChange,
  onStatus,
  openDataSources,
  openParameters,
  enabled = true,
  dataSourcesEnabled = true
}) {
  const ui = {
    close: root.querySelector("#dataset-close"),
    title: root.querySelector("#dataset-title"),
    subtitle: root.querySelector("#dataset-subtitle"),
    content: root.querySelector("#dataset-content")
  };
  let opener = null;
  let busy = false;
  let dirty = false;
  let datasets = [];
  let editDataset = null;
  let deleteTarget = null;
  let views = [];
  let inspectedFields = [];
  let validation = null;
  let discoveredFields = [];
  let discoveryFingerprint = "";
  let initialQueryFingerprint = "";
  let temporaryValues = {};
  let queryLengthLimit = 100000;

  applyIcon(ui.close, "close");
  ui.close.addEventListener("click", attemptClose);
  root.addEventListener("click", (event) => {
    if (event.target === root) {
      attemptClose();
    }
  });
  root.addEventListener("keydown", handleModalKeydown);

  return { open, close: attemptClose };

  async function open(openingControl = null) {
    if (!enabled) {
      onStatus?.("SQL dataset management is disabled.");
      return;
    }

    opener = openingControl || document.activeElement;
    resetTransientState();
    root.hidden = false;
    ui.close.focus();
    await showList();
  }

  function attemptClose() {
    if (busy) {
      return;
    }
    if (dirty && !window.confirm("Discard unsaved dataset changes?")) {
      return;
    }
    root.hidden = true;
    resetTransientState();
    opener?.focus?.();
  }

  async function showList() {
    dirty = false;
    editDataset = null;
    setHeading("Datasets", "MySQL views and read-only queries");
    setContentMessage("Loading datasets...", "status");
    try {
      const response = await listDatasets(getTemplate());
      datasets = response.datasets || [];
      renderDatasetList();
    } catch (error) {
      setContentMessage(error.message, "error");
    }
  }

  function renderDatasetList() {
    ui.content.replaceChildren();
    const sources = mysqlSources();
    const actions = element("div", "dataset-list-actions");
    const add = button("Add Dataset", "primary", () => showTypeSelection());
    add.disabled = sources.length === 0;
    actions.appendChild(add);
    ui.content.appendChild(actions);

    if (sources.length === 0) {
      const empty = messageBlock(
        "No MySQL data source is configured.",
        dataSourcesEnabled
          ? "Create and test a MySQL data source before adding a dataset."
          : "Data source management is disabled by the host application."
      );

      if (dataSourcesEnabled) {
        empty.appendChild(
          button("Open Data Sources", "", openDataSourceManager)
        );
      }

      ui.content.appendChild(empty);
      return;
    }

    if (datasets.length === 0) {
      ui.content.appendChild(messageBlock(
        "No datasets are configured.",
        "Add a dataset from an approved MySQL view or a read-only SELECT query."
      ));
      return;
    }
    const list = element("div", "dataset-list");
    for (const dataset of datasets) {
      list.appendChild(datasetCard(dataset));
    }
    ui.content.appendChild(list);
  }

  function datasetCard(dataset) {
    const card = element("article", "dataset-card");
    card.dataset.datasetId = dataset.id;
    const heading = element("div", "dataset-card-heading");
    const name = document.createElement("h3");
    name.textContent = dataset.name;
    const kind = document.createElement("span");
    kind.textContent = dataset.sourceType === "view" ? "Reporting View" : "Read-Only Query";
    heading.append(name, kind);
    const summary = element("dl", "dataset-summary");
    appendSummary(summary, dataset.sourceType === "view" ? "View" : "Source", dataset.sourceLabel);
    appendSummary(summary, "Data source", dataset.dataSourceName || dataset.dataSourceId);
    appendSummary(summary, "Fields", String(dataset.fieldCount));
    appendSummary(summary, "Parameters", String(dataset.parameterCount));
    const actions = element("div", "dataset-card-actions");
    const parameterAction = dataset.sourceType === "query"
      ? button("Parameters", "", (event) => openParameters(dataset.id, event.currentTarget))
      : null;
    actions.append(
      button("Fields", "", () => showFields(dataset.id)),
      dataset.sourceType === "view"
        ? button("Check Fields", "", () => refreshView(dataset.id))
        : button("Validate", "", () => validateStoredQuery(dataset.id)),
      ...(parameterAction ? [parameterAction] : []),
      button("Edit", "", () => edit(dataset.id)),
      button("Delete", "danger", () => showDelete(dataset))
    );
    card.append(heading, summary, actions);
    return card;
  }

  function showTypeSelection() {
    dirty = false;
    setHeading("Add Dataset", "Choose a MySQL dataset type");
    ui.content.replaceChildren();
    const choices = element("div", "dataset-type-grid");
    choices.append(
      typeChoice(
        "Reporting View",
        "Create a dataset from an approved MySQL reporting view and import its columns.",
        () => showViewForm()
      ),
      typeChoice(
        "Custom SELECT Query",
        "Create a dataset from one validated read-only SELECT query.",
        () => showQueryForm()
      )
    );
    ui.content.append(choices, formFooter(button("Back", "", showList)));
  }

  function typeChoice(title, description, action) {
    const choice = button("", "dataset-type-choice", action);
    const heading = document.createElement("strong");
    heading.textContent = title;
    const copy = document.createElement("span");
    copy.textContent = description;
    choice.append(heading, copy);
    return choice;
  }

  async function edit(datasetId) {
    setContentMessage("Loading dataset...", "status");
    try {
      const response = await getDataset(getTemplate(), datasetId);
      editDataset = response.dataset;
      if (editDataset.sourceType === "view") {
        await showViewForm(editDataset);
      } else {
        showQueryForm(editDataset);
      }
    } catch (error) {
      setContentMessage(error.message, "error");
    }
  }

  async function showViewForm(dataset = null) {
    editDataset = dataset;
    dirty = false;
    inspectedFields = dataset?.fields ? structuredClone(dataset.fields) : [];
    setHeading(dataset ? "Edit View Dataset" : "Add View Dataset", "Approved MySQL reporting views only");
    ui.content.innerHTML = viewFormMarkup();
    const form = ui.content.querySelector("#view-dataset-form");
    populateSourceSelect(form.elements.dataSourceId, dataset?.dataSourceId);
    form.elements.name.value = dataset?.name || "";
    if (dataset) {
      form.elements.dataSourceId.disabled = true;
    }
    bindViewForm(form);
    renderViewFields();
    await loadViews(form, dataset?.viewName || "");
    form.elements.name.focus();
  }

  function bindViewForm(form) {
    form.addEventListener("input", () => { dirty = true; });
    form.addEventListener("submit", saveViewForm);
    form.elements.cancel.addEventListener("click", showList);
    form.elements.dataSourceId.addEventListener("change", async () => {
      dirty = true;
      inspectedFields = [];
      await loadViews(form, "");
      renderViewFields();
    });
    form.elements.viewName.addEventListener("change", async () => {
      dirty = true;
      inspectedFields = [];
      renderViewFields("Inspecting view columns...");
      await inspectSelectedView(form);
    });
    form.elements.viewSearch.addEventListener("input", () => filterViews(form));
    form.elements.refreshViews.addEventListener("click", () => loadViews(form, form.elements.viewName.value));
  }

  async function loadViews(form, selected) {
    const sourceId = form.elements.dataSourceId.value;
    const status = form.querySelector("[data-view-status]");
    form.elements.viewName.disabled = true;
    form.elements.refreshViews.disabled = true;
    status.textContent = "Loading approved MySQL views...";
    try {
      const response = await listReportingViews(getTemplate(), sourceId);
      views = response.views || [];
      renderViewOptions(form, selected);
      status.textContent = views.length
        ? `${views.length} approved ${views.length === 1 ? "view" : "views"}`
        : "No approved reporting views were found.";
    } catch (error) {
      views = [];
      renderViewOptions(form, "");
      status.textContent = error.message;
      status.classList.add("is-error");
    } finally {
      form.elements.viewName.disabled = false;
      form.elements.refreshViews.disabled = false;
    }
  }

  function renderViewOptions(form, selected) {
    const select = form.elements.viewName;
    select.replaceChildren(new Option("Select a reporting view", ""));
    for (const view of views) {
      select.appendChild(new Option(view.displayName || view.viewName, view.viewName));
    }
    select.value = selected;
  }

  function filterViews(form) {
    const query = form.elements.viewSearch.value.trim().toLowerCase();
    const selected = form.elements.viewName.value;
    const filtered = views.filter((view) => view.viewName.toLowerCase().includes(query));
    const select = form.elements.viewName;
    select.replaceChildren(new Option("Select a reporting view", ""));
    for (const view of filtered) {
      select.appendChild(new Option(view.displayName || view.viewName, view.viewName));
    }
    if (filtered.some((view) => view.viewName === selected)) {
      select.value = selected;
    }
    form.querySelector("[data-view-status]").textContent = query
      ? `${filtered.length} matching views from ${views.length} approved views`
      : `${views.length} approved ${views.length === 1 ? "view" : "views"}`;
  }

  async function inspectSelectedView(form) {
    const viewName = form.elements.viewName.value;
    if (!viewName) {
      renderViewFields();
      return;
    }
    setBusy(form, true);
    try {
      const response = await inspectReportingView(
        getTemplate(), form.elements.dataSourceId.value, viewName
      );
      if (form.elements.viewName.value !== viewName) {
        return;
      }
      inspectedFields = response.fields || [];
      renderViewFields();
    } catch (error) {
      inspectedFields = [];
      renderViewFields("The selected reporting view could not be inspected.", error.message);
    } finally {
      setBusy(form, false);
    }
  }

  function renderViewFields(message = "", detail = "") {
    const container = ui.content.querySelector("[data-view-fields]");
    if (!container) {
      return;
    }
    if (message) {
      container.replaceChildren(messageBlock(message, detail));
    } else {
      renderFieldTable(container, inspectedFields, true);
    }
    const save = ui.content.querySelector('[name="save"]');
    if (save) {
      save.disabled = inspectedFields.length === 0;
    }
  }

  async function saveViewForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    clearFormError(form);
    if (!form.reportValidity() || inspectedFields.length === 0) {
      showFormError(form, "Select and inspect an approved reporting view before saving.");
      return;
    }
    const values = { name: form.elements.name.value.trim() };
    if (!editDataset) {
      Object.assign(values, {
        dataSourceId: form.elements.dataSourceId.value,
        viewName: form.elements.viewName.value
      });
    } else if (form.elements.viewName.value !== editDataset.viewName) {
      Object.assign(values, {
        viewName: form.elements.viewName.value,
        refreshFields: true
      });
    }
    await runMutation(form, async () => editDataset
      ? updateViewDataset(getTemplate(), editDataset.id, values)
      : createViewDataset(getTemplate(), values),
    editDataset ? "Edit dataset" : "Add dataset");
  }

  function showQueryForm(dataset = null) {
    editDataset = dataset;
    dirty = false;
    validation = null;
    discoveredFields = dataset?.fields ? structuredClone(dataset.fields) : [];
    discoveryFingerprint = "";
    temporaryValues = {};
    setHeading(dataset ? "Edit Query Dataset" : "Add Query Dataset", "One read-only MySQL SELECT query");
    ui.content.innerHTML = queryFormMarkup();
    const form = ui.content.querySelector("#query-dataset-form");
    populateSourceSelect(form.elements.dataSourceId, dataset?.dataSourceId);
    form.elements.name.value = dataset?.name || "";
    form.elements.query.value = dataset?.query || "";
    form._parameters = structuredClone(dataset?.parameters || []);
    form._detected = [];
    if (dataset) {
      form.elements.dataSourceId.disabled = true;
    }
    initialQueryFingerprint = queryConfigurationFingerprint(form.elements.query.value, form._parameters);
    bindQueryForm(form);
    renderQueryState(form);
    form.elements.name.focus();
  }

  function bindQueryForm(form) {
    form.addEventListener("submit", saveQueryForm);
    form.elements.cancel.addEventListener("click", showList);
    form.elements.name.addEventListener("input", () => { dirty = true; });
    form.elements.dataSourceId.addEventListener("change", () => {
      dirty = true;
      temporaryValues = {};
      invalidateQueryState(form);
    });
    form.elements.query.addEventListener("input", () => {
      dirty = true;
      invalidateQueryState(form);
      renderQueryState(form);
    });
    form.elements.validate.addEventListener("click", () => validateQueryForm(form));
    form.elements.addMissing.addEventListener("click", () => {
      form._parameters = reconcileDetectedParameters(form._parameters, form._detected);
      dirty = true;
      validation = null;
      renderQueryState(form);
    });
    form.elements.discover.addEventListener("click", () => discoverQueryForm(form));
    form.elements.applyFields.addEventListener("click", () => applyFields(form));
    form.querySelector("[data-parameters]").addEventListener("change", () => {
      form._parameters = readParameterDefinitions(form);
      dirty = true;
      temporaryValues = {};
      invalidateQueryState(form);
      renderQueryState(form);
    });
    form.querySelector("[data-parameters]").addEventListener("input", () => {
      form._parameters = readParameterDefinitions(form);
      dirty = true;
      invalidateQueryState(form);
      updateQueryButtons(form);
    });
    form.querySelector("[data-temporary-values]").addEventListener("input", (event) => {
      temporaryValues[event.target.dataset.temporaryName] = event.target.value;
    });
  }

  function invalidateQueryState(form) {
    validation = null;
    discoveryFingerprint = "";
    if (form) {
      discoveredFields = editDataset?.fields ? structuredClone(editDataset.fields) : [];
    }
  }

  async function validateQueryForm(form) {
    clearFormError(form);
    const query = form.elements.query.value;
    if (!query.trim()) {
      showFormError(form, "Enter a read-only SELECT query.");
      return;
    }
    setBusy(form, true);
    const fingerprint = queryConfigurationFingerprint(query, form._parameters);
    try {
      const response = await validateDatasetQuery(getTemplate(), {
        query,
        parameters: form._parameters
      });
      if (fingerprint !== queryConfigurationFingerprint(
        form.elements.query.value, readParameterDefinitions(form)
      )) {
        return;
      }
      validation = { ...response, fingerprint };
      queryLengthLimit = response.maxQueryLength || queryLengthLimit;
      form._detected = response.parameters || [];
      renderQueryState(form);
    } catch (error) {
      validation = null;
      showFormError(form, error.message);
      renderQueryState(form);
    } finally {
      setBusy(form, false);
    }
  }

  async function discoverQueryForm(form) {
    form._parameters = readParameterDefinitions(form);
    if (!queryIsCurrent(form) || missingParameterNames(form).length) {
      showFormError(form, "Validate the query and define every detected parameter before discovery.");
      return;
    }
    const fingerprint = currentQueryFingerprint(form);
    setBusy(form, true);
    clearFormError(form);
    setQueryStatus(form, "Discovering query fields...", "loading");
    try {
      const response = await discoverDatasetQuery(getTemplate(), {
        dataSourceId: form.elements.dataSourceId.value,
        query: form.elements.query.value,
        parameters: form._parameters,
        parameterValues: readTemporaryValues(form)
      });
      if (fingerprint !== currentQueryFingerprint(form)) {
        showFormError(form, "The query changed after field discovery. Run discovery again.");
        return;
      }
      discoveredFields = response.fields || [];
      discoveryFingerprint = fingerprint;
      validation.warnings = response.warnings || validation.warnings;
      setQueryStatus(
        form,
        `${discoveredFields.length} fields discovered in ${Math.round(response.elapsedMs || 0)} ms.`,
        "success"
      );
      renderDiscoveredFields(form);
      updateQueryButtons(form);
    } catch (error) {
      discoveryFingerprint = "";
      showFormError(form, error.message);
      setQueryStatus(form, "Field discovery failed.", "error");
    } finally {
      setBusy(form, false);
    }
  }

  async function saveQueryForm(event) {
    event.preventDefault();
    const form = event.currentTarget;
    form._parameters = readParameterDefinitions(form);
    clearFormError(form);
    if (!form.reportValidity()) {
      return;
    }
    const configChanged = initialQueryFingerprint !== currentQueryFingerprint(form);
    if ((!editDataset || configChanged) && !discoveryIsCurrent(form)) {
      showFormError(form, "Discover the current query fields before saving the dataset.");
      return;
    }
    const values = { name: form.elements.name.value.trim() };
    if (!editDataset || configChanged) {
      Object.assign(values, {
        dataSourceId: form.elements.dataSourceId.value,
        query: form.elements.query.value,
        parameters: form._parameters,
        parameterValues: readTemporaryValues(form)
      });
    }
    await runMutation(form, async () => editDataset
      ? updateQueryDataset(getTemplate(), editDataset.id, values)
      : createQueryDataset(getTemplate(), values),
    editDataset ? "Edit dataset" : "Add dataset");
  }

  async function applyFields(form) {
    if (!editDataset || !discoveryIsCurrent(form) || currentQueryFingerprint(form) !== initialQueryFingerprint) {
      showFormError(form, "Save query changes before applying fields to this dataset.");
      return;
    }
    await runMutation(
      form,
      () => applyExistingDatasetFields(
        getTemplate(), editDataset.id, readTemporaryValues(form)
      ),
      "Apply dataset fields"
    );
  }

  function renderQueryState(form) {
    const count = form.querySelector("[data-query-count]");
    count.textContent = `${form.elements.query.value.length} / ${queryLengthLimit} characters`;
    renderValidation(form);
    renderParameters(form);
    renderTemporaryValues(form);
    renderDiscoveredFields(form);
    updateQueryButtons(form);
  }

  function renderValidation(form) {
    const container = form.querySelector("[data-validation-status]");
    container.className = "dataset-status";
    if (!validation) {
      container.textContent = form.elements.query.value.trim()
        ? "Query validation is required or stale."
        : "Enter a query, then validate it.";
      return;
    }
    container.classList.add("is-success");
    container.replaceChildren();
    const status = document.createElement("strong");
    status.textContent = "Valid read-only MySQL query";
    const details = document.createElement("span");
    details.textContent = `Statement: ${validation.statement}. Parameters: ${
      validation.parameters.length ? validation.parameters.join(", ") : "none"
    }`;
    container.append(status, details);
    for (const warning of validation.warnings || []) {
      const item = document.createElement("span");
      item.className = "field-warning";
      item.textContent = warning;
      container.appendChild(item);
    }
  }

  function renderParameters(form) {
    const container = form.querySelector("[data-parameters]");
    container.replaceChildren();
    const detected = form._detected || [];
    if (!detected.length && !form._parameters.length) {
      container.appendChild(messageBlock("No parameters detected.", "Validate the query to detect :name parameters."));
    } else {
      const table = document.createElement("table");
      table.className = "dataset-table parameter-table";
      table.innerHTML = "<thead><tr><th>Name</th><th>Type</th><th>Required</th><th>Default</th><th>Label</th></tr></thead>";
      const body = document.createElement("tbody");
      for (const parameter of form._parameters) {
        body.appendChild(parameterRow(parameter));
      }
      table.appendChild(body);
      container.appendChild(table);
    }
    const missing = missingParameterNames(form);
    form.elements.addMissing.hidden = missing.length === 0;
    form.elements.addMissing.textContent = missing.length
      ? `Add Missing Parameters (${missing.length})`
      : "Add Missing Parameters";
  }

  function parameterRow(parameter) {
    const row = document.createElement("tr");
    row.dataset.parameterName = parameter.name;
    const name = document.createElement("td");
    name.textContent = parameter.name;
    const typeCell = document.createElement("td");
    const type = document.createElement("select");
    type.dataset.parameterField = "dataType";
    type.setAttribute("aria-label", `${parameter.name} data type`);
    for (const item of PARAMETER_TYPES) {
      type.appendChild(new Option(item, item));
    }
    type.value = parameter.dataType || "string";
    typeCell.appendChild(type);
    const requiredCell = document.createElement("td");
    const required = document.createElement("input");
    required.type = "checkbox";
    required.checked = Boolean(parameter.required);
    required.dataset.parameterField = "required";
    required.setAttribute("aria-label", `${parameter.name} required`);
    requiredCell.appendChild(required);
    const defaultCell = document.createElement("td");
    defaultCell.appendChild(valueInput(parameter, "default"));
    const labelCell = document.createElement("td");
    const label = document.createElement("input");
    label.type = "text";
    label.value = parameter.label || "";
    label.dataset.parameterField = "label";
    label.setAttribute("aria-label", `${parameter.name} display label`);
    labelCell.appendChild(label);
    row.append(name, typeCell, requiredCell, defaultCell, labelCell);
    return row;
  }

  function renderTemporaryValues(form) {
    const container = form.querySelector("[data-temporary-values]");
    container.replaceChildren();
    if (!form._parameters.length) {
      container.appendChild(messageBlock("No temporary values required.", ""));
      return;
    }
    const grid = element("div", "temporary-value-grid");
    for (const parameter of form._parameters) {
      const label = element("label", "dataset-field");
      const text = document.createElement("span");
      text.textContent = parameter.label || parameterLabel(parameter.name);
      const input = valueInput(parameter, "temporary");
      input.dataset.temporaryName = parameter.name;
      input.value = temporaryValues[parameter.name] ?? "";
      label.append(text, input);
      grid.appendChild(label);
    }
    container.appendChild(grid);
  }

  function renderDiscoveredFields(form) {
    const hasDatabaseMetadata = discoveredFields.some((field) => field.databaseType);
    renderFieldTable(
      form.querySelector("[data-discovered-fields]"),
      discoveredFields,
      hasDatabaseMetadata
    );
  }

  function updateQueryButtons(form) {
    const valid = queryIsCurrent(form) && missingParameterNames(form).length === 0;
    form.elements.discover.disabled = busy || !valid;
    form.elements.applyFields.hidden = !editDataset;
    form.elements.applyFields.disabled = busy || !discoveryIsCurrent(form)
      || currentQueryFingerprint(form) !== initialQueryFingerprint;
    const configChanged = initialQueryFingerprint !== currentQueryFingerprint(form);
    form.elements.save.disabled = busy || ((!editDataset || configChanged) && !discoveryIsCurrent(form));
  }

  function queryIsCurrent(form) {
    return Boolean(validation && validation.fingerprint === currentQueryFingerprint(form));
  }

  function discoveryIsCurrent(form) {
    return Boolean(discoveryFingerprint && discoveryFingerprint === currentQueryFingerprint(form));
  }

  function currentQueryFingerprint(form) {
    return queryConfigurationFingerprint(form.elements.query.value, form._parameters);
  }

  function missingParameterNames(form) {
    const declared = new Set(form._parameters.map((item) => item.name.toLowerCase()));
    return (form._detected || []).filter((name) => !declared.has(name.toLowerCase()));
  }

  function readParameterDefinitions(form) {
    return [...form.querySelectorAll("[data-parameter-name]")].map((row) => {
      const type = row.querySelector('[data-parameter-field="dataType"]').value;
      const defaultControl = row.querySelector('[data-parameter-field="default"]');
      const parameter = {
        name: row.dataset.parameterName,
        dataType: type,
        required: row.querySelector('[data-parameter-field="required"]').checked,
        label: row.querySelector('[data-parameter-field="label"]').value.trim()
      };
      const defaultValue = typedValue(defaultControl.value, type);
      if (defaultValue !== undefined) {
        parameter.default = defaultValue;
      }
      return parameter;
    });
  }

  function readTemporaryValues(form) {
    const result = {};
    for (const control of form.querySelectorAll("[data-temporary-name]")) {
      const parameter = form._parameters.find((item) => item.name === control.dataset.temporaryName);
      const value = typedValue(control.value, parameter?.dataType || "string");
      if (value !== undefined) {
        result[control.dataset.temporaryName] = value;
      }
    }
    return result;
  }

  function typedValue(value, type) {
    if (value === "") {
      return undefined;
    }
    if (type === "integer") {
      return Number.parseInt(value, 10);
    }
    if (type === "float") {
      return Number(value);
    }
    if (type === "boolean") {
      return value === "true";
    }
    return value;
  }

  function valueInput(parameter, purpose) {
    const value = purpose === "default" ? parameter.default : "";
    let input;
    if (parameter.dataType === "boolean") {
      input = document.createElement("select");
      input.append(new Option("No value", ""), new Option("True", "true"), new Option("False", "false"));
      input.value = value === true ? "true" : value === false ? "false" : "";
    } else {
      input = document.createElement("input");
      input.type = inputType(parameter.dataType);
      if (["integer", "float"].includes(parameter.dataType)) {
        input.step = parameter.dataType === "integer" ? "1" : "any";
      }
      input.value = value ?? "";
    }
    if (purpose === "default") {
      input.dataset.parameterField = "default";
      input.setAttribute("aria-label", `${parameter.name} default value`);
    } else {
      input.setAttribute("aria-label", `${parameter.name} temporary discovery value`);
    }
    return input;
  }

  function inputType(type) {
    return ({ integer: "number", float: "number", date: "date", time: "time", datetime: "datetime-local" })[type] || "text";
  }

  async function showFields(datasetId) {
    setContentMessage("Loading stored fields...", "status");
    try {
      const response = await getDataset(getTemplate(), datasetId);
      const dataset = response.dataset;
      setHeading(`Dataset Fields - ${dataset.name}`, "Stored field definitions; no rows are fetched");
      ui.content.replaceChildren();
      const container = element("div", "dataset-fields-viewer");
      renderFieldTable(container, dataset.fields || [], false);
      const actions = [];
      if (dataset.sourceType === "view") {
        actions.push(button("Check View Fields", "", () => refreshView(dataset.id)));
      } else {
        actions.push(button("Edit and Discover", "", () => showQueryForm(dataset)));
      }
      actions.push(button("Back", "", showList));
      ui.content.append(container, formFooter(...actions));
    } catch (error) {
      setContentMessage(error.message, "error");
    }
  }

  async function refreshView(datasetId) {
    setContentMessage("Checking current view fields...", "status");
    try {
      const freshness = await checkDatasetFreshness(getTemplate(), datasetId);
      if (freshness.fresh) {
        onStatus("View dataset fields are current.");
        await showFields(datasetId);
        return;
      }
      const summary = [
        `Added: ${freshness.addedFields.length}`,
        `Removed: ${freshness.removedFields.length}`,
        `Changed: ${freshness.changedFields.length}`,
        `Bound objects affected: ${freshness.affectedObjectIds.length}`
      ].join("\n");
      if (!window.confirm(`Dataset fields have changed.\n\n${summary}\n\nApply new fields?`)) {
        await showFields(datasetId);
        return;
      }
      const response = await refreshViewDatasetFields(getTemplate(), datasetId);
      applyMutationResponse(response, "Refresh dataset fields", response.message);
      renderChangeSummary(response.changes);
    } catch (error) {
      setContentMessage(error.message, "error");
    }
  }

  async function validateStoredQuery(datasetId) {
    try {
      const response = await getDataset(getTemplate(), datasetId);
      const dataset = response.dataset;
      await validateDatasetQuery(getTemplate(), {
        query: dataset.query,
        parameters: dataset.parameters || []
      });
      onStatus("Dataset query is valid.");
    } catch (error) {
      onStatus(error.message);
    }
  }

  function showDelete(dataset) {
    deleteTarget = dataset;
    dirty = false;
    setHeading("Delete dataset?", "This action affects only the active report");
    ui.content.replaceChildren();
    const warning = messageBlock(
      `The dataset "${dataset.name}" will be removed from this report.`,
      "Future report objects may depend on its fields. The parent data source will remain."
    );
    const cancel = button("Cancel", "", showList);
    const confirm = button("Delete", "danger-solid", removeDataset);
    ui.content.append(warning, formFooter(cancel, confirm));
    cancel.focus();
  }

  async function removeDataset() {
    if (!deleteTarget) {
      return;
    }
    setContentMessage("Deleting dataset...", "status");
    try {
      const response = await deleteDataset(getTemplate(), deleteTarget.id);
      applyMutationResponse(response, "Delete dataset", response.message);
      await showList();
    } catch (error) {
      setContentMessage(error.message, "error");
    }
  }

  async function runMutation(form, operation, historyLabel) {
    setBusy(form, true);
    clearFormError(form);
    try {
      const response = await operation();
      applyMutationResponse(response, historyLabel, response.message);
      await showList();
    } catch (error) {
      showFormError(form, error.message);
    } finally {
      setBusy(form, false);
    }
  }

  function applyMutationResponse(response, historyLabel, status) {
    if (!response.template) {
      throw new Error("The dataset operation did not return an updated report.");
    }
    onTemplateChange(response.template, historyLabel, status || "Dataset updated.");
    dirty = false;
  }

  function renderChangeSummary(changes) {
    if (!changes || ![...changes.added, ...changes.removed, ...changes.changed].length) {
      onStatus("View fields refreshed with no changes.");
      showList();
      return;
    }
    setHeading("Field Changes", "Refreshing fields may affect future report field bindings");
    ui.content.replaceChildren();
    for (const [label, items] of Object.entries(changes)) {
      if (!items.length) {
        continue;
      }
      const section = element("section", "dataset-change-group");
      const heading = document.createElement("h3");
      heading.textContent = `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
      const list = document.createElement("ul");
      for (const item of items) {
        const entry = document.createElement("li");
        entry.textContent = item;
        list.appendChild(entry);
      }
      section.append(heading, list);
      ui.content.appendChild(section);
    }
    ui.content.appendChild(formFooter(button("Done", "primary", showList)));
  }

  function renderFieldTable(container, fields, includeDatabaseType) {
    container.replaceChildren();
    if (!fields.length) {
      container.appendChild(messageBlock("No fields are stored.", "Discover or inspect fields before saving."));
      return;
    }
    const scroll = element("div", "dataset-table-scroll");
    const table = document.createElement("table");
    table.className = "dataset-table";
    table.innerHTML = includeDatabaseType
      ? "<thead><tr><th>#</th><th>Name</th><th>MySQL Type</th><th>Report Type</th><th>Nullable</th><th>Size</th><th>Comment</th></tr></thead>"
      : "<thead><tr><th>#</th><th>Name</th><th>Report Type</th><th>Nullable</th><th>Source</th></tr></thead>";
    const body = document.createElement("tbody");
    fields.forEach((field, index) => {
      const row = document.createElement("tr");
      const values = includeDatabaseType
        ? [index + 1, field.name, field.databaseType || "", field.dataType, nullableLabel(field.nullable), fieldSize(field), field.comment || ""]
        : [index + 1, field.name, field.dataType, nullableLabel(field.nullable), field.sourceName || ""];
      for (const value of values) {
        const cell = document.createElement("td");
        cell.textContent = String(value ?? "");
        row.appendChild(cell);
      }
      if (field.warning) {
        row.classList.add("has-warning");
        row.title = field.warning;
      }
      body.appendChild(row);
    });
    table.appendChild(body);
    scroll.appendChild(table);
    container.appendChild(scroll);
  }

  function populateSourceSelect(select, selected = "") {
    select.replaceChildren();
    for (const source of mysqlSources()) {
      select.appendChild(new Option(source.name, source.id));
    }
    if (selected) {
      select.value = selected;
    }
  }

  function mysqlSources() {
    return (getTemplate()?.dataSources || []).filter((source) => source.type === "mysql");
  }

  function openDataSourceManager() {
    if (!dataSourcesEnabled) {
      onStatus?.("Data source management is disabled.");
      return;
    }

    root.hidden = true;
    resetTransientState();
    openDataSources?.();
  }

  function setBusy(form, value) {
    busy = value;
    if (!form) {
      return;
    }
    for (const control of form.querySelectorAll("button, select")) {
      if (control.name !== "cancel") {
        control.disabled = value;
      }
    }
    if (!value) {
      form.elements.dataSourceId.disabled = Boolean(editDataset);
      if (form.id === "query-dataset-form") {
        updateQueryButtons(form);
      } else if (form.id === "view-dataset-form") {
        form.elements.save.disabled = inspectedFields.length === 0;
      }
    }
  }

  function showFormError(form, message) {
    const error = form.querySelector("[data-form-error]");
    error.hidden = false;
    error.textContent = message;
  }

  function clearFormError(form) {
    const error = form.querySelector("[data-form-error]");
    error.hidden = true;
    error.textContent = "";
  }

  function setQueryStatus(form, message, state) {
    const status = form.querySelector("[data-discovery-status]");
    status.textContent = message;
    status.className = `dataset-status is-${state}`;
  }

  function setContentMessage(message, state) {
    ui.content.replaceChildren();
    const item = element("div", `dataset-message is-${state}`);
    item.setAttribute(state === "error" ? "role" : "aria-live", state === "error" ? "alert" : "polite");
    item.textContent = message;
    ui.content.appendChild(item);
  }

  function setHeading(title, subtitle) {
    ui.title.textContent = title;
    ui.subtitle.textContent = subtitle;
  }

  function resetTransientState() {
    dirty = false;
    busy = false;
    editDataset = null;
    deleteTarget = null;
    views = [];
    inspectedFields = [];
    validation = null;
    discoveredFields = [];
    discoveryFingerprint = "";
    temporaryValues = {};
  }

  function handleModalKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      attemptClose();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    const controls = focusableControls(root);
    if (!controls.length) {
      return;
    }
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

function viewFormMarkup() {
  return `
    <form id="view-dataset-form" class="dataset-form" novalidate>
      <div class="dataset-form-grid">
        <label class="dataset-field"><span>Dataset Name</span><input name="name" required autocomplete="off"></label>
        <label class="dataset-field"><span>MySQL Data Source</span><select name="dataSourceId" required></select></label>
        <label class="dataset-field"><span>Search Views</span><input name="viewSearch" type="search" autocomplete="off"></label>
        <label class="dataset-field"><span>Reporting View</span><select name="viewName" required></select></label>
      </div>
      <div class="dataset-inline-actions">
        <span data-view-status role="status"></span>
        <button name="refreshViews" class="toolbar-button" type="button">Refresh View List</button>
      </div>
      <div class="dataset-section"><h3>View Fields</h3><div data-view-fields></div></div>
      <div class="dataset-message is-error" data-form-error role="alert" hidden></div>
      <footer class="dataset-form-actions">
        <button name="cancel" class="toolbar-button" type="button">Cancel</button>
        <button name="save" class="toolbar-button primary" type="submit" disabled>Save Dataset</button>
      </footer>
    </form>`;
}

function queryFormMarkup() {
  return `
    <form id="query-dataset-form" class="dataset-form query-dataset-form" novalidate>
      <div class="dataset-form-grid">
        <label class="dataset-field"><span>Dataset Name</span><input name="name" required autocomplete="off"></label>
        <label class="dataset-field"><span>MySQL Data Source</span><select name="dataSourceId" required></select></label>
      </div>
      <section class="dataset-section">
        <div class="dataset-section-heading"><h3>Read-Only SELECT Query</h3><span data-query-count></span></div>
        <label class="sr-only" for="dataset-query-editor">Read-only SELECT query</label>
        <textarea id="dataset-query-editor" name="query" class="sql-editor" required spellcheck="false" autocomplete="off" autocapitalize="off"></textarea>
        <div class="dataset-inline-actions">
          <span>Only one read-only SELECT or WITH...SELECT query is permitted. Use :name parameters.</span>
          <button name="validate" class="toolbar-button" type="button">Validate Query</button>
        </div>
        <div class="dataset-status" data-validation-status role="status"></div>
      </section>
      <section class="dataset-section">
        <div class="dataset-section-heading"><h3>Parameter Definitions</h3><button name="addMissing" class="toolbar-button" type="button" hidden>Add Missing Parameters</button></div>
        <div data-parameters></div>
      </section>
      <section class="dataset-section">
        <h3>Temporary Values for Field Discovery</h3>
        <div data-temporary-values></div>
      </section>
      <section class="dataset-section">
        <div class="dataset-section-heading"><h3>Discovered Fields</h3><div class="dataset-inline-actions"><button name="discover" class="toolbar-button" type="button" disabled>Discover Fields</button><button name="applyFields" class="toolbar-button" type="button" hidden disabled>Apply Fields</button></div></div>
        <div data-discovery-status class="dataset-status" role="status"></div>
        <div data-discovered-fields></div>
      </section>
      <div class="dataset-message is-error" data-form-error role="alert" hidden></div>
      <footer class="dataset-form-actions">
        <button name="cancel" class="toolbar-button" type="button">Cancel</button>
        <button name="save" class="toolbar-button primary" type="submit" disabled>Save Dataset</button>
      </footer>
    </form>`;
}

function element(tag, className = "") {
  const item = document.createElement(tag);
  item.className = className;
  return item;
}

function button(label, variant, action) {
  const item = document.createElement("button");
  item.type = "button";
  item.className = `toolbar-button ${variant}`.trim();
  item.textContent = label;
  if (action) {
    item.addEventListener("click", action);
  }
  return item;
}

function formFooter(...controls) {
  const footer = element("footer", "dataset-form-actions");
  footer.append(...controls);
  return footer;
}

function messageBlock(title, detail) {
  const container = element("div", "dataset-empty");
  const heading = document.createElement("strong");
  heading.textContent = title;
  const copy = document.createElement("p");
  copy.textContent = detail;
  container.append(heading, copy);
  return container;
}

function appendSummary(container, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value ?? "";
  container.append(term, description);
}

function nullableLabel(value) {
  return value === true ? "Yes" : value === false ? "No" : "Unknown";
}

function fieldSize(field) {
  if (field.precision !== null && field.precision !== undefined) {
    return field.scale !== null && field.scale !== undefined
      ? `${field.precision}, ${field.scale}`
      : String(field.precision);
  }
  return field.length !== null && field.length !== undefined ? String(field.length) : "";
}

function focusableControls(root) {
  return [...root.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
  )].filter((item) => !item.hidden && item.offsetParent !== null);
}

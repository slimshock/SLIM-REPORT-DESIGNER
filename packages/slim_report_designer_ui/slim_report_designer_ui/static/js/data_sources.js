import {
  clearRuntimeCredentials,
  createMysqlDataSource,
  deleteMysqlDataSource,
  listDataSources,
  testMysqlDataSource,
  testSavedMysqlDataSource,
  updateMysqlDataSource
} from "./api.js";
import { applyIcon } from "./icons.js";

export const MYSQL_DEFAULTS = Object.freeze({
  name: "",
  host: "localhost",
  port: 3306,
  database: "",
  username: "",
  credentialMode: "passwordRef",
  password: "",
  passwordRef: "",
  charset: "utf8mb4",
  connectTimeout: 10,
  queryTimeout: 30
});

export function validateDataSourceValues(values, options = {}) {
  const errors = {};
  for (const [key, label] of [
    ["name", "Data source name"],
    ["host", "Host"],
    ["database", "Database"],
    ["username", "Username"],
    ["charset", "Charset"]
  ]) {
    if (!String(values[key] || "").trim()) {
      errors[key] = `${label} is required.`;
    }
  }
  const port = Number(values.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    errors.port = "Port must be an integer from 1 to 65535.";
  }
  for (const [key, label] of [
    ["connectTimeout", "Connection timeout"],
    ["queryTimeout", "Query timeout"]
  ]) {
    const value = Number(values[key]);
    if (!Number.isInteger(value) || value < 1) {
      errors[key] = `${label} must be a positive integer.`;
    }
  }
  if (values.credentialMode === "passwordRef" && !String(values.passwordRef || "").trim()) {
    errors.passwordRef = "Password reference is required.";
  }
  if (
    values.credentialMode === "runtimePassword"
    && options.requireRuntimePassword
    && !String(values.password || "")
  ) {
    errors.password = "Password is required for runtime password mode.";
  }
  if (!["runtimePassword", "passwordRef", "none"].includes(values.credentialMode)) {
    errors.credentialMode = "Choose a credential method.";
  }
  return errors;
}

export function normalizeDataSourceValues(values, runtimePassword = null) {
  const mode = String(values.credentialMode || "none");
  return {
    name: String(values.name || "").trim(),
    host: String(values.host || "").trim(),
    port: Number(values.port),
    database: String(values.database || "").trim(),
    username: String(values.username || "").trim(),
    credentialMode: mode,
    password: mode === "runtimePassword" ? String(values.password || runtimePassword || "") : null,
    passwordRef: mode === "passwordRef" ? String(values.passwordRef || "").trim() : null,
    clearRuntimePassword: mode !== "runtimePassword",
    clearPasswordRef: mode !== "passwordRef",
    charset: String(values.charset || "").trim(),
    connectTimeout: Number(values.connectTimeout),
    queryTimeout: Number(values.queryTimeout)
  };
}

export function credentialStatusLabel(source, runtimeConfigured = false) {
  if (source?.credentialStatus?.message && !runtimeConfigured) {
    return source.credentialStatus.message;
  }
  if (runtimeConfigured || source?.passwordConfigured) {
    return "Runtime password configured";
  }
  if (source?.passwordRefConfigured) {
    return "Environment reference configured";
  }
  return "No password configured";
}

export function createDataSourceManager({ root, getTemplate, onTemplateChange, onStatus }) {
  const ui = managerElements(root);
  const runtimePasswords = new Map();
  const testStates = new Map();
  let sources = [];
  let opener = null;
  let busy = false;
  let editId = null;
  let deleteId = null;
  let formBaseline = "";
  let formRuntimePassword = null;
  let formInitialRuntimePassword = null;

  applyIcon(ui.close, "close");
  ui.close.addEventListener("click", () => attemptClose());
  ui.add.addEventListener("click", () => openForm());
  ui.formCancel.addEventListener("click", () => returnToList());
  ui.deleteCancel.addEventListener("click", () => returnToList());
  ui.deleteConfirm.addEventListener("click", () => removeSelectedSource());
  ui.test.addEventListener("click", () => testFormConnection());
  ui.form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveForm();
  });
  ui.form.addEventListener("change", (event) => {
    if (event.target?.name === "credentialMode") {
      renderCredentialMode(ui.form.elements.credentialMode.value);
    }
  });
  ui.list.addEventListener("click", (event) => handleListAction(event));
  root.addEventListener("click", (event) => {
    if (event.target === root) {
      attemptClose();
    }
  });
  root.addEventListener("keydown", handleModalKeydown);

  return {
    open,
    close: attemptClose,
    clearRuntimePasswords: async () => {
      runtimePasswords.clear();
      await clearRuntimeCredentials();
    }
  };

  async function open(openingControl = null) {
    opener = openingControl || document.activeElement;
    root.hidden = false;
    showView("list");
    ui.listStatus.hidden = false;
    ui.listStatus.className = "data-source-message";
    ui.listStatus.textContent = "Loading MySQL data sources...";
    ui.list.replaceChildren();
    ui.close.focus();
    await refreshList();
  }

  function attemptClose() {
    if (busy) {
      return;
    }
    if (isFormDirty() && !window.confirm("Discard unsaved data-source changes?")) {
      return;
    }
    root.hidden = true;
    resetFormState();
    opener?.focus?.();
  }

  async function refreshList() {
    try {
      const response = await listDataSources(getTemplate());
      sources = response.dataSources || [];
      renderList();
    } catch (error) {
      ui.listStatus.hidden = false;
      ui.listStatus.className = "data-source-message is-error";
      ui.listStatus.textContent = error.message;
    }
  }

  function renderList() {
    ui.list.replaceChildren();
    if (sources.length === 0) {
      ui.listStatus.hidden = false;
      ui.listStatus.className = "data-source-message is-empty";
      ui.listStatus.textContent = "No MySQL data sources are configured.";
      return;
    }
    ui.listStatus.hidden = true;
    for (const source of sources) {
      ui.list.appendChild(sourceCard(source));
    }
  }

  function sourceCard(source) {
    const card = document.createElement("article");
    card.className = "data-source-card";
    card.dataset.sourceId = source.id;

    const heading = document.createElement("div");
    heading.className = "data-source-card-heading";
    const title = document.createElement("h3");
    title.textContent = source.name;
    const endpoint = document.createElement("span");
    endpoint.textContent = `${source.host}:${source.port} / ${source.database}`;
    heading.append(title, endpoint);

    const details = document.createElement("dl");
    details.className = "data-source-summary";
    appendSummary(details, "Username", source.username);
    appendSummary(
      details,
      "Credential",
      credentialStatusLabel(source, runtimePasswords.has(source.id))
    );
    appendSummary(details, "Charset", source.charset);
    appendSummary(
      details,
      "Timeouts",
      `${source.connectTimeout}s connect / ${source.queryTimeout}s query`
    );

    const testState = testStates.get(source.id) || { state: "idle", message: "Not tested" };
    const status = document.createElement("div");
    status.className = `connection-state is-${testState.state}`;
    status.setAttribute("role", "status");
    status.textContent = testState.message;
    if (testState.warnings?.length) {
      const warning = document.createElement("span");
      warning.textContent = testState.warnings.join(" ");
      status.appendChild(warning);
    }

    const actions = document.createElement("div");
    actions.className = "data-source-card-actions";
    actions.append(
      actionButton("test", "Test", source.id),
      actionButton("edit", "Edit", source.id),
      actionButton("delete", "Delete", source.id, "danger")
    );
    if (runtimePasswords.has(source.id) || source.credentialStatus?.source === "runtime") {
      actions.insertBefore(
        actionButton("clearCredential", "Clear Runtime Password", source.id),
        actions.lastChild
      );
    }
    if (testState.state === "testing") {
      actions.querySelector('[data-action="test"]').disabled = true;
    }
    card.append(heading, details, status, actions);
    return card;
  }

  async function handleListAction(event) {
    const button = event.target.closest("button[data-action]");
    if (!button || busy) {
      return;
    }
    const source = sources.find((item) => item.id === button.dataset.sourceId);
    if (!source) {
      return;
    }
    if (button.dataset.action === "edit") {
      openForm(source);
    } else if (button.dataset.action === "delete") {
      openDelete(source);
    } else if (button.dataset.action === "test") {
      await testSavedSource(source);
    } else if (button.dataset.action === "clearCredential") {
      await clearSourceCredential(source);
    }
  }

  async function clearSourceCredential(source) {
    await clearRuntimeCredentials(source.id);
    runtimePasswords.delete(source.id);
    testStates.delete(source.id);
    source.passwordConfigured = false;
    if (source.credentialStatus) {
      source.credentialStatus = {
        configured: source.passwordRefConfigured,
        resolved: !source.passwordRefConfigured,
        source: source.passwordRefConfigured ? null : "none",
        message: source.passwordRefConfigured
          ? "Credential could not be resolved."
          : "No password is configured."
      };
    }
    renderList();
    onStatus("Runtime password cleared.");
  }

  function openForm(source = null) {
    editId = source?.id || null;
    deleteId = null;
    formRuntimePassword = editId ? runtimePasswords.get(editId) || null : null;
    formInitialRuntimePassword = formRuntimePassword;
    const config = editId ? sourceConfig(getTemplate(), editId) : null;
    const values = sourceFormValues(source, config, runtimePasswords.has(editId));
    setFormValues(ui.form, values);
    ui.formTitle.textContent = source ? "Edit MySQL Data Source" : "Add MySQL Data Source";
    ui.credentialStatus.textContent = source
      ? credentialStatusLabel(source, runtimePasswords.has(source.id))
      : "Credential values are never stored in the report template.";
    ui.formError.hidden = true;
    ui.testResult.hidden = true;
    clearFieldErrors();
    renderCredentialMode(values.credentialMode);
    formBaseline = formFingerprint();
    showView("form");
    ui.form.elements.name.focus();
  }

  function sourceFormValues(source, config, hasRuntimePassword) {
    if (!source) {
      return { ...MYSQL_DEFAULTS };
    }
    const passwordRef = config?.passwordRef || config?.password_ref || "";
    const credentialMode = passwordRef
      ? "passwordRef"
      : (hasRuntimePassword || source.passwordConfigured ? "runtimePassword" : "none");
    return {
      name: source.name || "",
      host: source.host || "",
      port: source.port || 3306,
      database: source.database || "",
      username: source.username || "",
      credentialMode,
      password: "",
      passwordRef,
      charset: source.charset || config?.charset || "utf8mb4",
      connectTimeout: source.connectTimeout || config?.connectTimeout || 10,
      queryTimeout: source.queryTimeout || config?.queryTimeout || 30
    };
  }

  function renderCredentialMode(mode) {
    ui.runtimePasswordField.hidden = mode !== "runtimePassword";
    ui.passwordReferenceField.hidden = mode !== "passwordRef";
  }

  async function testFormConnection() {
    if (busy) {
      return;
    }
    const values = readFormValues(ui.form);
    const errors = validateDataSourceValues(values, {
      requireRuntimePassword: values.credentialMode === "runtimePassword"
        && !formRuntimePassword
    });
    if (!showValidationErrors(errors)) {
      return;
    }
    if (values.credentialMode === "runtimePassword" && values.password) {
      formRuntimePassword = values.password;
    }
    const payload = normalizeDataSourceValues(values, formRuntimePassword);
    setBusy(true, "testing");
    showTestMessage("testing", "Testing connection...");
    try {
      const result = await testMysqlDataSource(payload);
      renderConnectionResult(result);
      onStatus(result.success ? "Connection successful." : "Connection failed.");
    } catch (error) {
      showTestMessage("failed", error.message || "Connection failed.");
      onStatus("Connection failed.");
    } finally {
      ui.form.elements.password.value = "";
      setBusy(false);
    }
  }

  async function saveForm() {
    if (busy) {
      return;
    }
    const values = readFormValues(ui.form);
    const errors = validateDataSourceValues(values, {
      requireRuntimePassword: values.credentialMode === "runtimePassword"
        && !formRuntimePassword
    });
    if (!showValidationErrors(errors)) {
      return;
    }
    if (values.credentialMode === "runtimePassword" && values.password) {
      formRuntimePassword = values.password;
    }
    const payload = normalizeDataSourceValues(values, formRuntimePassword);
    setBusy(true, "saving");
    ui.formError.hidden = true;
    try {
      const response = editId
        ? await updateMysqlDataSource(getTemplate(), editId, payload)
        : await createMysqlDataSource(getTemplate(), payload);
      const sourceId = response.source?.id || editId;
      if (payload.credentialMode === "runtimePassword" && payload.password && sourceId) {
        runtimePasswords.set(sourceId, payload.password);
      } else if (sourceId) {
        runtimePasswords.delete(sourceId);
      }
      if (editId) {
        testStates.delete(editId);
      }
      onTemplateChange(
        response.template,
        editId ? "Edit MySQL data source" : "Add MySQL data source",
        response.message
      );
      sources = response.dataSources || [];
      resetFormState();
      showView("list");
      renderList();
      onStatus(response.message);
      ui.add.focus();
    } catch (error) {
      ui.formError.hidden = false;
      ui.formError.textContent = error.message;
      ui.form.elements.password.value = "";
    } finally {
      setBusy(false);
    }
  }

  async function testSavedSource(source) {
    testStates.set(source.id, { state: "testing", message: "Testing connection..." });
    renderList();
    try {
      const result = await testSavedMysqlDataSource(
        getTemplate(),
        source.id,
        runtimePasswords.get(source.id) || null
      );
      testStates.set(source.id, testStateFromResult(result));
      onStatus(result.success ? "Connection successful." : "Connection failed.");
    } catch (error) {
      testStates.set(source.id, { state: "failed", message: error.message });
      onStatus("Connection failed.");
    }
    renderList();
  }

  function openDelete(source) {
    deleteId = source.id;
    editId = null;
    ui.deleteMessage.textContent = `The data source "${source.name}" will be removed from this report.`;
    ui.deleteError.hidden = true;
    showView("delete");
    ui.deleteCancel.focus();
  }

  async function removeSelectedSource() {
    if (!deleteId || busy) {
      return;
    }
    const sourceId = deleteId;
    setBusy(true, "deleting");
    ui.deleteError.hidden = true;
    try {
      const response = await deleteMysqlDataSource(getTemplate(), sourceId);
      runtimePasswords.delete(sourceId);
      testStates.delete(sourceId);
      onTemplateChange(response.template, "Delete MySQL data source", response.message);
      sources = response.dataSources || [];
      deleteId = null;
      showView("list");
      renderList();
      onStatus(response.message);
      ui.add.focus();
    } catch (error) {
      ui.deleteError.hidden = false;
      const dependents = error.dependents?.length
        ? ` Used by: ${error.dependents.join(", ")}.`
        : "";
      ui.deleteError.textContent = `${error.message}${dependents}`;
    } finally {
      setBusy(false);
    }
  }

  function returnToList() {
    if (busy) {
      return;
    }
    if (isFormDirty() && !window.confirm("Discard unsaved data-source changes?")) {
      return;
    }
    resetFormState();
    showView("list");
    renderList();
    ui.add.focus();
  }

  function resetFormState() {
    editId = null;
    deleteId = null;
    formBaseline = "";
    formRuntimePassword = null;
    formInitialRuntimePassword = null;
    ui.form.reset();
    ui.formError.hidden = true;
    ui.testResult.hidden = true;
    clearFieldErrors();
  }

  function showView(view) {
    ui.listView.hidden = view !== "list";
    ui.formView.hidden = view !== "form";
    ui.deleteView.hidden = view !== "delete";
  }

  function setBusy(value, operation = "") {
    busy = value;
    for (const control of root.querySelectorAll("button, input")) {
      control.disabled = value;
    }
    if (!value) {
      ui.save.textContent = "Save";
      ui.test.textContent = "Test Connection";
      ui.deleteConfirm.textContent = "Delete";
      return;
    }
    if (operation === "saving") {
      ui.save.textContent = "Saving data source...";
    } else if (operation === "testing") {
      ui.test.textContent = "Testing connection...";
    } else if (operation === "deleting") {
      ui.deleteConfirm.textContent = "Removing data source...";
    }
  }

  function showValidationErrors(errors) {
    clearFieldErrors();
    for (const [field, message] of Object.entries(errors)) {
      const output = root.querySelector(`[data-error-for="${field}"]`);
      if (output) {
        output.textContent = message;
      }
    }
    const firstField = Object.keys(errors)[0];
    if (firstField) {
      ui.form.elements[firstField]?.focus?.();
      return false;
    }
    return true;
  }

  function clearFieldErrors() {
    for (const output of root.querySelectorAll("[data-error-for]")) {
      output.textContent = "";
    }
  }

  function showTestMessage(state, message) {
    ui.testResult.hidden = false;
    ui.testResult.className = `connection-test-result is-${state}`;
    ui.testResult.replaceChildren();
    const heading = document.createElement("strong");
    heading.textContent = message;
    ui.testResult.appendChild(heading);
  }

  function renderConnectionResult(result) {
    showTestMessage(result.success ? "connected" : "failed", result.message);
    const details = document.createElement("dl");
    details.className = "connection-result-details";
    appendSummary(details, "Provider", result.provider);
    appendSummary(details, "Database", result.database || "Not reported");
    if (result.serverVersion) {
      appendSummary(details, "Server", result.serverVersion);
    }
    appendSummary(details, "Read-only verified", result.readOnlyVerified ? "Yes" : "No");
    if (result.elapsedMs !== null && result.elapsedMs !== undefined) {
      appendSummary(details, "Elapsed", `${Number(result.elapsedMs).toFixed(1)} ms`);
    }
    ui.testResult.appendChild(details);
    if (result.warnings?.length) {
      const warnings = document.createElement("p");
      warnings.textContent = result.warnings.join(" ");
      ui.testResult.appendChild(warnings);
    }
  }

  function formFingerprint() {
    const values = readFormValues(ui.form);
    values.password = "";
    return JSON.stringify(values);
  }

  function isFormDirty() {
    return !ui.formView.hidden
      && Boolean(formBaseline)
      && (
        formFingerprint() !== formBaseline
        || Boolean(ui.form.elements.password.value)
        || formRuntimePassword !== formInitialRuntimePassword
      );
  }

  function handleModalKeydown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      if (!busy) {
        if (ui.listView.hidden) {
          returnToList();
        } else {
          attemptClose();
        }
      }
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

function managerElements(root) {
  return {
    close: root.querySelector("#data-source-close"),
    listView: root.querySelector("#data-source-list-view"),
    formView: root.querySelector("#data-source-form-view"),
    deleteView: root.querySelector("#data-source-delete-view"),
    add: root.querySelector("#data-source-add"),
    listStatus: root.querySelector("#data-source-list-status"),
    list: root.querySelector("#data-source-list"),
    form: root.querySelector("#data-source-form"),
    formTitle: root.querySelector("#data-source-form-title"),
    credentialStatus: root.querySelector("#data-source-credential-status"),
    formError: root.querySelector("#data-source-form-error"),
    runtimePasswordField: root.querySelector("#runtime-password-field"),
    passwordReferenceField: root.querySelector("#password-reference-field"),
    testResult: root.querySelector("#data-source-test-result"),
    test: root.querySelector("#data-source-test"),
    formCancel: root.querySelector("#data-source-form-cancel"),
    save: root.querySelector("#data-source-save"),
    deleteMessage: root.querySelector("#data-source-delete-message"),
    deleteError: root.querySelector("#data-source-delete-error"),
    deleteCancel: root.querySelector("#data-source-delete-cancel"),
    deleteConfirm: root.querySelector("#data-source-delete-confirm")
  };
}

function sourceConfig(template, dataSourceId) {
  const source = (template?.dataSources || []).find((item) => item.id === dataSourceId);
  return source?.connection || null;
}

function setFormValues(form, values) {
  for (const [key, value] of Object.entries(values)) {
    const control = form.elements[key];
    if (!control) {
      continue;
    }
    if (key === "credentialMode") {
      const option = form.querySelector(`[name="credentialMode"][value="${value}"]`);
      if (option) {
        option.checked = true;
      }
    } else {
      control.value = value ?? "";
    }
  }
}

function readFormValues(form) {
  const values = Object.fromEntries(new FormData(form).entries());
  return {
    ...MYSQL_DEFAULTS,
    ...values,
    credentialMode: form.elements.credentialMode.value
  };
}

function appendSummary(container, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value ?? "";
  container.append(term, description);
}

function actionButton(action, label, sourceId, variant = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `toolbar-button ${variant}`.trim();
  button.dataset.action = action;
  button.dataset.sourceId = sourceId;
  button.textContent = label;
  return button;
}

function testStateFromResult(result) {
  if (!result.success) {
    return { state: "failed", message: result.message, warnings: result.warnings || [] };
  }
  if (!result.readOnlyVerified) {
    return {
      state: "warning",
      message: "Connected - read-only unverified",
      warnings: result.warnings || []
    };
  }
  return { state: "connected", message: "Connected", warnings: result.warnings || [] };
}

function focusableControls(root) {
  return [...root.querySelectorAll("button, input, summary, [tabindex]")]
    .filter((control) => !control.disabled && !control.hidden && control.offsetParent !== null);
}

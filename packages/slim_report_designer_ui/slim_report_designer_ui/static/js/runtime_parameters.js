import { getRuntimeParameterSchema, validateRuntimeParameters } from "./api.js";
import { applyIcon } from "./icons.js";

const INPUT_TYPES = Object.freeze({
  integer: "number",
  float: "number",
  date: "date",
  time: "time",
  datetime: "datetime-local"
});

export function createRuntimeParameterDialog({ root, getTemplate, onStatus }) {
  const ui = {
    title: root.querySelector("#runtime-parameter-title"),
    subtitle: root.querySelector("#runtime-parameter-subtitle"),
    close: root.querySelector("#runtime-parameter-close"),
    form: root.querySelector("#runtime-parameter-form"),
    fields: root.querySelector("#runtime-parameter-fields"),
    status: root.querySelector("#runtime-parameter-status"),
    defaults: root.querySelector("#runtime-parameter-defaults"),
    clear: root.querySelector("#runtime-parameter-clear"),
    cancel: root.querySelector("#runtime-parameter-cancel"),
    validate: root.querySelector("#runtime-parameter-validate")
  };
  let schema = null;
  let datasetId = "";
  let opener = null;
  let pending = null;
  let resolvePending = null;
  let completeOnValid = false;
  let busy = false;

  applyIcon(ui.close, "close");
  ui.close.addEventListener("click", cancel);
  ui.cancel.addEventListener("click", cancel);
  ui.defaults.addEventListener("click", applyDefaults);
  ui.clear.addEventListener("click", clearValues);
  ui.form.addEventListener("submit", validate);
  root.addEventListener("click", (event) => {
    if (event.target === root) {
      cancel();
    }
  });
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      cancel();
      return;
    }
    if (event.key === "Tab") {
      const controls = focusableControls(root);
      if (controls.length === 0) {
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
  });

  return { open, close: cancel, collectRuntimeParameters };

  function open(id, options = {}) {
    return start(id, { ...options, completeOnValid: false });
  }

  function collectRuntimeParameters(id, options = {}) {
    return start(id, { ...options, completeOnValid: true });
  }

  async function start(id, options) {
    if (!root.hidden) {
      finish({ cancelled: true });
    }
    datasetId = String(id || "");
    opener = options.openingControl || document.activeElement;
    completeOnValid = Boolean(options.completeOnValid);
    ui.validate.textContent = options.actionLabel || "Validate Parameters";
    root.hidden = false;
    setBusy(true);
    setStatus("Loading parameter definitions...", "");
    ui.fields.replaceChildren();
    pending = new Promise((resolve) => {
      resolvePending = resolve;
    });
    try {
      schema = await getRuntimeParameterSchema(getTemplate(), datasetId);
      renderSchema();
    } catch (error) {
      schema = null;
      setStatus(error.message, "error");
    } finally {
      setBusy(false);
    }
    return pending;
  }

  function renderSchema() {
    ui.title.textContent = "Report Parameters";
    ui.subtitle.textContent = schema.datasetName || "Query dataset";
    ui.fields.replaceChildren();
    const parameters = schema.parameters || [];
    if (parameters.length === 0) {
      const empty = document.createElement("p");
      empty.className = "runtime-parameter-empty";
      empty.textContent = "This query does not require runtime parameters.";
      ui.fields.appendChild(empty);
      ui.validate.disabled = false;
      setStatus("No parameter values are required.", "success");
      ui.cancel.focus();
      return;
    }
    for (const parameter of parameters) {
      ui.fields.appendChild(parameterField(parameter));
    }
    applyDefaults();
    const firstMissing = parameters.find((parameter) => parameter.required && !parameter.hasDefault);
    const target = firstMissing || parameters[0];
    inputFor(target.name)?.focus();
  }

  function parameterField(parameter) {
    const wrapper = document.createElement("div");
    wrapper.className = "runtime-parameter-field";
    wrapper.dataset.parameterName = parameter.name;

    const label = document.createElement("label");
    label.htmlFor = controlId(parameter.name);
    const labelText = document.createElement("span");
    labelText.className = "runtime-parameter-label";
    labelText.textContent = parameter.label;
    if (parameter.required) {
      const marker = document.createElement("span");
      marker.className = "required-marker";
      marker.textContent = " *";
      marker.setAttribute("aria-hidden", "true");
      labelText.appendChild(marker);
    }
    const metadata = document.createElement("span");
    metadata.className = "runtime-parameter-meta";
    metadata.title = `:${parameter.name}`;
    metadata.textContent = `:${parameter.name} | ${parameter.dataType} | ${parameter.required ? "Required" : "Optional"}${parameter.hasDefault ? " | Configured default" : ""}`;
    label.append(labelText, metadata);

    const input = createInput(parameter);
    input.id = controlId(parameter.name);
    input.name = parameter.name;
    input.dataset.parameterInput = parameter.name;
    input.autocomplete = "off";
    input.required = Boolean(parameter.required && parameter.dataType === "boolean");
    input.setAttribute("aria-required", String(Boolean(parameter.required)));
    input.setAttribute("aria-describedby", `${controlId(parameter.name)}-error`);

    const error = document.createElement("span");
    error.id = `${controlId(parameter.name)}-error`;
    error.className = "runtime-parameter-error";
    error.dataset.parameterError = parameter.name;
    error.setAttribute("role", "alert");
    wrapper.append(label, input, error);
    return wrapper;
  }

  function createInput(parameter) {
    if (parameter.dataType === "boolean") {
      const select = document.createElement("select");
      if (!parameter.required) {
        select.appendChild(new Option("No value", ""));
      } else {
        select.appendChild(new Option("Select a value", ""));
      }
      select.append(new Option("True", "true"), new Option("False", "false"));
      return select;
    }
    const input = document.createElement("input");
    input.type = INPUT_TYPES[parameter.dataType] || "text";
    if (parameter.dataType === "integer") {
      input.step = "1";
      input.inputMode = "numeric";
    } else if (parameter.dataType === "float") {
      input.step = "any";
    } else if (parameter.dataType === "decimal") {
      input.type = "text";
      input.inputMode = "decimal";
    }
    if (parameter.dataType === "string") {
      input.maxLength = 100000;
    }
    return input;
  }

  function applyDefaults() {
    for (const parameter of schema?.parameters || []) {
      const input = inputFor(parameter.name);
      input.value = parameter.hasDefault ? displayValue(parameter.default, parameter.dataType) : "";
    }
    clearErrors();
    setStatus("Configured defaults restored.", "");
  }

  function clearValues() {
    for (const input of ui.fields.querySelectorAll("[data-parameter-input]")) {
      input.value = "";
    }
    clearErrors();
    setStatus("Values cleared.", "");
    firstInput()?.focus();
  }

  async function validate(event) {
    event.preventDefault();
    if (busy || !schema) {
      return;
    }
    clearErrors();
    const values = readValues();
    const localIssue = localValidationIssue(values);
    if (localIssue) {
      showIssues([localIssue]);
      return;
    }
    setBusy(true);
    setStatus("Validating parameters...", "");
    try {
      const result = await validateRuntimeParameters(getTemplate(), datasetId, values);
      if (!result.valid) {
        showIssues(result.errors || []);
        return;
      }
      const defaults = (result.usedDefaults || []).length;
      setStatus(`Parameters are valid. ${result.parameterCount} resolved; ${defaults} configured default${defaults === 1 ? "" : "s"} used.`, "success");
      onStatus("Runtime parameters are valid.");
      if (completeOnValid) {
        const collected = { ...values };
        closeAndClear();
        finish({ cancelled: false, values: collected });
      }
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      setBusy(false);
    }
  }

  function readValues() {
    const values = {};
    for (const input of ui.fields.querySelectorAll("[data-parameter-input]")) {
      values[input.dataset.parameterInput] = input.value;
    }
    return values;
  }

  function localValidationIssue(values) {
    for (const parameter of schema.parameters || []) {
      const value = values[parameter.name];
      if (parameter.required && value === "" && !parameter.hasDefault) {
        return issue(parameter, "missing_required", `The required parameter "${parameter.label}" has no value.`);
      }
      if (value === "") {
        continue;
      }
      if (parameter.dataType === "integer" && !/^[+-]?\d+$/.test(value)) {
        return issue(parameter, "invalid_integer", `The parameter "${parameter.label}" must be a valid integer.`);
      }
      if (parameter.dataType === "decimal" && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value)) {
        return issue(parameter, "invalid_decimal", `The parameter "${parameter.label}" must be a valid decimal.`);
      }
    }
    return null;
  }

  function issue(parameter, code, message) {
    return { parameter: parameter.name, code, message };
  }

  function showIssues(issues) {
    const first = issues[0];
    for (const item of issues) {
      const target = ui.fields.querySelector(`[data-parameter-error="${cssEscape(item.parameter || "")}"]`);
      if (target) {
        target.textContent = item.message;
        target.closest(".runtime-parameter-field")?.classList.add("is-invalid");
      }
    }
    setStatus(first?.message || "Parameter validation failed.", "error");
    if (first?.parameter) {
      inputFor(first.parameter)?.focus();
    }
  }

  function clearErrors() {
    for (const error of ui.fields.querySelectorAll("[data-parameter-error]")) {
      error.textContent = "";
      error.closest(".runtime-parameter-field")?.classList.remove("is-invalid");
    }
  }

  function cancel() {
    if (busy) {
      return;
    }
    closeAndClear();
    finish({ cancelled: true });
  }

  function closeAndClear() {
    root.hidden = true;
    ui.fields.replaceChildren();
    setStatus("", "");
    schema = null;
    datasetId = "";
    ui.validate.textContent = "Validate Parameters";
    opener?.focus?.();
    opener = null;
  }

  function finish(result) {
    const resolve = resolvePending;
    resolvePending = null;
    pending = null;
    resolve?.(result);
  }

  function setBusy(value) {
    busy = value;
    ui.validate.disabled = value;
    ui.defaults.disabled = value;
    ui.clear.disabled = value;
    ui.cancel.disabled = value;
    ui.close.disabled = value;
  }

  function setStatus(message, kind) {
    ui.status.textContent = message;
    ui.status.className = `runtime-parameter-status${kind ? ` is-${kind}` : ""}`;
  }

  function inputFor(name) {
    return ui.fields.querySelector(`[data-parameter-input="${cssEscape(name)}"]`);
  }

  function firstInput() {
    return ui.fields.querySelector("[data-parameter-input]");
  }
}

function displayValue(value, type) {
  if (value === null || value === undefined) {
    return "";
  }
  if (type === "boolean") {
    const normalized = String(value).toLowerCase();
    return value === true || value === 1 || ["true", "yes", "1"].includes(normalized)
      ? "true"
      : "false";
  }
  return String(value);
}

function controlId(name) {
  return `runtime-parameter-${String(name).replace(/[^A-Za-z0-9_-]/g, "-")}`;
}

function cssEscape(value) {
  return window.CSS?.escape
    ? window.CSS.escape(String(value))
    : String(value).replace(/["\\]/g, "\\$&");
}

function focusableControls(root) {
  return [...root.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
    '[tabindex]:not([tabindex="-1"])'
  )].filter((item) => !item.hidden && item.offsetParent !== null);
}

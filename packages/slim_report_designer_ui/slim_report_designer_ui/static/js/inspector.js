import { objectStyle, setObjectBinding, setObjectText } from "./objects.js";

const COMMON_FIELDS = [
  ["id", "text"],
  ["type", "text", true],
  ["x", "number"],
  ["y", "number"],
  ["width", "number"],
  ["height", "number"]
];

export function createInspector({ form, getSelectedObject, onChange, onSelect }) {
  form.addEventListener("input", (event) => {
    const input = event.target;
    if (!input.name) {
      return;
    }
    const object = getSelectedObject();
    if (!object) {
      return;
    }
    applyInput(object, input);
    onChange({ inspectorOnly: input.name === "id" });
    if (input.name === "id") {
      onSelect(object.id);
    }
  });

  return {
    render() {
      renderInspector(form, getSelectedObject());
    }
  };
}

export function renderInspector(form, object) {
  form.innerHTML = "";
  if (!object) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Select an object to edit its properties.";
    form.appendChild(empty);
    return;
  }

  for (const [name, type, readonly] of COMMON_FIELDS) {
    form.appendChild(fieldRow(name, object[name], { type, readonly }));
  }

  if (object.type === "text") {
    form.appendChild(fieldRow("text", object.text || object.properties?.text || ""));
    form.appendChild(styleField("font_size", object, "number"));
    form.appendChild(styleField("bold", object, "checkbox"));
  } else if (object.type === "field") {
    form.appendChild(fieldRow("binding", object.binding || object.properties?.binding || ""));
    form.appendChild(styleField("font_size", object, "number"));
    form.appendChild(styleField("bold", object, "checkbox"));
  } else if (object.type === "rectangle") {
    form.appendChild(styleField("border_width", object, "number"));
  } else if (object.type === "line") {
    form.appendChild(styleField("stroke_width", object, "number"));
  }
}

function applyInput(object, input) {
  const value = input.type === "checkbox" ? input.checked : input.value;
  const numericFields = new Set(["x", "y", "width", "height"]);
  if (numericFields.has(input.name)) {
    object[input.name] = Number(value) || 0;
    return;
  }
  if (input.dataset.styleKey) {
    const style = objectStyle(object);
    style[input.dataset.styleKey] = input.type === "number" ? Number(value) || 0 : value;
    return;
  }
  if (input.name === "text") {
    setObjectText(object, String(value));
    return;
  }
  if (input.name === "binding") {
    setObjectBinding(object, String(value));
    return;
  }
  object[input.name] = String(value);
}

function styleField(name, object, type) {
  const style = objectStyle(object);
  return fieldRow(name, style[name] ?? defaultStyleValue(name), {
    type,
    styleKey: name
  });
}

function fieldRow(name, value, options = {}) {
  const row = document.createElement("div");
  row.className = options.type === "checkbox" ? "field-row checkbox-row" : "field-row";

  const label = document.createElement("label");
  label.htmlFor = `inspector-${name}`;
  label.textContent = name;

  const input = document.createElement("input");
  input.id = `inspector-${name}`;
  input.name = name;
  input.type = options.type || "text";
  input.readOnly = Boolean(options.readonly);
  if (options.styleKey) {
    input.dataset.styleKey = options.styleKey;
  }
  if (input.type === "checkbox") {
    input.checked = Boolean(value);
    row.append(input, label);
  } else {
    input.value = value ?? "";
    row.append(label, input);
  }
  return row;
}

function defaultStyleValue(name) {
  if (name === "font_size") {
    return 12;
  }
  if (name === "border_width" || name === "stroke_width") {
    return 1;
  }
  return "";
}

import { objectStyle, setObjectBinding, setObjectText } from "./objects.js";

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
    onChange();
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

  form.appendChild(section("Identity", [
    fieldRow("id", object.id, { disabled: true }),
    fieldRow("type", object.type, { disabled: true })
  ]));
  form.appendChild(section("Position", [
    fieldRow("x", object.x, { type: "number" }),
    fieldRow("y", object.y, { type: "number" })
  ], "field-grid"));
  form.appendChild(section("Size", [
    fieldRow("width", object.width, { type: "number" }),
    fieldRow("height", object.height, { type: "number" })
  ], "field-grid"));

  if (object.type === "text") {
    form.appendChild(section("Content", [
      fieldRow("text", object.text || object.properties?.text || "")
    ]));
    form.appendChild(section("Style", [
      styleField("font_size", object, "number"),
      styleField("bold", object, "checkbox")
    ]));
  } else if (object.type === "field") {
    form.appendChild(section("Content", [
      fieldRow("binding", object.binding || object.properties?.binding || "")
    ]));
    form.appendChild(section("Style", [
      styleField("font_size", object, "number"),
      styleField("bold", object, "checkbox")
    ]));
  } else if (object.type === "rectangle") {
    form.appendChild(section("Style", [
      styleField("border_width", object, "number")
    ]));
  } else if (object.type === "line") {
    form.appendChild(section("Style", [
      styleField("stroke_width", object, "number")
    ]));
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
  input.disabled = Boolean(options.disabled);
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

function section(title, rows, className = "") {
  const group = document.createElement("fieldset");
  group.className = `inspector-section ${className}`.trim();

  const legend = document.createElement("legend");
  legend.textContent = title;
  group.appendChild(legend);

  for (const row of rows) {
    group.appendChild(row);
  }
  return group;
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

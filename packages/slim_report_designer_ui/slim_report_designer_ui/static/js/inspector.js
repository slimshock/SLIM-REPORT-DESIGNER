import { icon } from "./icons.js";
import { objectStyle, setObjectBinding, setObjectStyleValue, setObjectText } from "./objects.js";

export function createInspector({ form, getSelectedObject, onChange }) {
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
  form.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-style-key]");
    if (!button) {
      return;
    }
    const object = getSelectedObject();
    if (!object) {
      return;
    }
    event.preventDefault();
    setObjectStyleValue(object, button.dataset.styleKey, button.dataset.styleValue);
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
    form.appendChild(section("Style", textStyleFields(object)));
  } else if (object.type === "field") {
    form.appendChild(section("Content", [
      fieldRow("binding", object.binding || object.properties?.binding || "")
    ]));
    form.appendChild(section("Style", textStyleFields(object)));
  } else if (object.type === "rectangle") {
    form.appendChild(section("Style", [
      styleField("border_width", object, "number"),
      styleField("border_color", object, "color"),
      styleField("background_color", object, "color", { label: "background", transparent: true })
    ]));
  } else if (object.type === "line") {
    form.appendChild(section("Style", [
      styleField("stroke_width", object, "number"),
      styleField("stroke_color", object, "color")
    ]));
  }
}

function textStyleFields(object) {
  return [
    styleField("font_family", object, "select", { options: fontFamilyOptions() }),
    styleField("font_size", object, "number"),
    styleField("bold", object, "checkbox"),
    styleField("italic", object, "checkbox"),
    styleField("underline", object, "checkbox"),
    styleField("color", object, "color", { label: "text color" }),
    styleField("background_color", object, "color", { label: "background", transparent: true }),
    toggleField("align", object, [
      ["left", "Left", "align-left"],
      ["center", "Center", "align-center"],
      ["right", "Right", "align-right"]
    ]),
    toggleField("vertical_align", object, [
      ["top", "Top", "align-top"],
      ["middle", "Middle", "align-middle"],
      ["bottom", "Bottom", "align-bottom"]
    ], "vertical align")
  ];
}

function applyInput(object, input) {
  const value = input.type === "checkbox" ? input.checked : input.value;
  const numericFields = new Set(["x", "y", "width", "height"]);
  if (numericFields.has(input.name)) {
    object[input.name] = Number(value) || 0;
    return;
  }
  if (input.dataset.styleKey) {
    setObjectStyleValue(object, input.dataset.styleKey, inputValue(input, value));
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

function inputValue(input, value) {
  if (input.type === "number") {
    return Number(value) || 0;
  }
  if (input.type === "checkbox") {
    return Boolean(value);
  }
  return value;
}

function styleField(name, object, type, options = {}) {
  const style = objectStyle(object);
  return fieldRow(options.label || name, style[name] ?? defaultStyleValue(name), {
    type,
    name,
    styleKey: name,
    options: options.options,
    transparent: options.transparent
  });
}

function toggleField(name, object, values, label = name) {
  const style = objectStyle(object);
  const current = style[name] ?? defaultStyleValue(name);
  const row = document.createElement("div");
  row.className = "field-row toggle-row";

  const labelElement = document.createElement("span");
  labelElement.className = "field-label";
  labelElement.textContent = label;

  const group = document.createElement("div");
  group.className = "toggle-group";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", label);

  for (const [value, title, iconName] of values) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toggle-button";
    button.dataset.styleKey = name;
    button.dataset.styleValue = value;
    button.title = title;
    button.setAttribute("aria-label", title);
    button.innerHTML = `${icon(iconName)}<span class="sr-only">${title}</span>`;
    if (current === value) {
      button.classList.add("is-active");
      button.setAttribute("aria-pressed", "true");
    } else {
      button.setAttribute("aria-pressed", "false");
    }
    group.appendChild(button);
  }

  row.append(labelElement, group);
  return row;
}

function fieldRow(labelText, value, options = {}) {
  const name = options.name || labelText;
  const row = document.createElement("div");
  row.className = options.type === "checkbox" ? "field-row checkbox-row" : "field-row";
  if (options.type === "color") {
    row.classList.add("color-row");
  }

  const label = document.createElement("label");
  label.htmlFor = `inspector-${name}`;
  label.textContent = labelText;

  const input = options.type === "select" ? document.createElement("select") : document.createElement("input");
  input.id = `inspector-${name}`;
  input.name = name;
  if (input instanceof HTMLInputElement) {
    input.type = options.type || "text";
  }
  input.disabled = Boolean(options.disabled);
  if (options.styleKey) {
    input.dataset.styleKey = options.styleKey;
  }

  if (input instanceof HTMLSelectElement) {
    for (const optionValue of options.options || []) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      input.appendChild(option);
    }
    input.value = value ?? "";
    row.append(label, input);
  } else if (input.type === "checkbox") {
    input.checked = Boolean(value);
    row.append(input, label);
  } else if (input.type === "color") {
    input.value = colorInputValue(value);
    row.append(label, input, colorValue(value));
    if (options.transparent) {
      row.append(transparentButton(name));
    }
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
  if (name === "font_family") {
    return "Arial";
  }
  if (name === "font_size") {
    return 12;
  }
  if (name === "color" || name === "border_color" || name === "stroke_color") {
    return "#111827";
  }
  if (name === "background_color") {
    return "transparent";
  }
  if (name === "align") {
    return "left";
  }
  if (name === "vertical_align") {
    return "top";
  }
  if (name === "border_width" || name === "stroke_width") {
    return 1;
  }
  if (name === "bold" || name === "italic" || name === "underline") {
    return false;
  }
  return "";
}

function colorInputValue(value) {
  return /^#[0-9a-f]{6}$/i.test(String(value)) ? String(value) : "#ffffff";
}

function colorValue(value) {
  const output = document.createElement("span");
  output.className = "color-value";
  output.textContent = String(value || "transparent");
  return output;
}

function transparentButton(name) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "transparent-button";
  button.dataset.styleKey = name;
  button.dataset.styleValue = "transparent";
  button.textContent = "transparent";
  button.title = "Use transparent background";
  return button;
}

function fontFamilyOptions() {
  return ["Arial", "Helvetica", "Times-Roman", "Courier"];
}

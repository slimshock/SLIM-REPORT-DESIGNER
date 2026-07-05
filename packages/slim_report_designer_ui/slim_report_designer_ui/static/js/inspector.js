import { icon } from "./icons.js";
import {
  objectStyle,
  setObjectAlt,
  setObjectBinding,
  setObjectPropertyValue,
  setObjectSource,
  setObjectStyleValue,
  setObjectText,
  setPageOrientation,
  setPageSize,
  setPageUnit,
  setPageValue
} from "./objects.js";

export function createInspector({
  form,
  getTemplate,
  getSelectedObject,
  onBeforeChange = () => {},
  onChange
}) {
  form.addEventListener("input", (event) => {
    const input = event.target;
    if (!input.name) {
      return;
    }
    if (input instanceof HTMLInputElement && input.type === "file") {
      return;
    }
    const object = getSelectedObject();
    onBeforeChange("Edit properties");
    if (!object) {
      applyPageInput(getTemplate(), input);
      onChange({ preserveInspector: shouldPreserveInspectorFocus(input) });
      return;
    }
    applyInput(object, input);
    onChange({ preserveInspector: shouldPreserveInspectorFocus(input) });
  });
  form.addEventListener("change", async (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "file" || input.name !== "image_upload") {
      return;
    }
    const object = getSelectedObject();
    const file = input.files?.[0];
    if (!object || object.type !== "image" || !file) {
      return;
    }
    onBeforeChange("Upload image");
    setObjectSource(object, await readFileAsDataUrl(file));
    input.value = "";
    onChange();
  });
  form.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-style-key]");
    if (!button) {
      return;
    }
    const object = getSelectedObject();
    if (!object) {
      const template = getTemplate();
      if (button.dataset.pageKey) {
        event.preventDefault();
        onBeforeChange("Edit page background");
        setPageValue(template, button.dataset.pageKey, button.dataset.styleValue);
        if (button.dataset.pageKey === "background_color") {
          setPageValue(template, "transparent", true);
        }
        onChange();
      }
      return;
    }
    event.preventDefault();
    onBeforeChange("Edit style");
    setObjectStyleValue(object, button.dataset.styleKey, button.dataset.styleValue);
    onChange();
  });

  return {
    render() {
      renderInspector(form, getSelectedObject(), getTemplate());
    }
  };
}

export function renderInspector(form, object, template = {}) {
  form.innerHTML = "";
  if (!object) {
    form.appendChild(renderPageInspector(template));
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
  } else if (object.type === "image") {
    form.appendChild(section("Content", [
      fieldRow("source_mode", object.properties?.source_mode || "url", {
        type: "select",
        options: ["url", "upload"],
        name: "source_mode"
      }),
      fieldRow("Image URL", object.src || object.properties?.src || object.properties?.source || "", {
        name: "src"
      }),
      fieldRow("Upload image", "", {
        type: "file",
        name: "image_upload",
        accept: "image/png,image/jpeg,image/webp,image/svg+xml"
      }),
      fieldRow("Alt text", object.alt || object.properties?.alt || "", { name: "alt" })
    ]));
    form.appendChild(section("Style", [
      styleField("object_fit", object, "select", { options: ["contain", "cover", "fill"] }),
      styleField("opacity", object, "number", { step: "0.05", min: "0", max: "1" }),
      styleField("border_radius", object, "number"),
      styleField("border_width", object, "number"),
      styleField("border_color", object, "color"),
      styleField("background_color", object, "color", { label: "background", transparent: true }),
      fieldRow("maintain_aspect_ratio", Boolean(object.properties?.maintain_aspect_ratio ?? true), {
        type: "checkbox",
        name: "maintain_aspect_ratio"
      })
    ]));
  }
}

function renderPageInspector(template) {
  const page = template.page || {};
  const fragment = document.createDocumentFragment();
  fragment.appendChild(section("Page Properties", [
    fieldRow("report name", template.metadata?.title || template.metadata?.name || "", { name: "report_name" }),
    fieldRow("paper size", page.size || "A4", {
      type: "select",
      name: "page.size",
      options: ["A4", "Letter", "Legal", "Custom"]
    }),
    fieldRow("orientation", page.orientation || "portrait", {
      type: "select",
      name: "page.orientation",
      options: ["portrait", "landscape"]
    }),
    fieldRow("unit", page.unit || "px", {
      type: "select",
      name: "page.unit",
      options: ["px", "mm", "in"]
    })
  ]));
  fragment.appendChild(section("Page Size", [
    fieldRow("width", page.width, { type: "number", name: "page.width" }),
    fieldRow("height", page.height, { type: "number", name: "page.height" })
  ], "field-grid"));
  fragment.appendChild(section("Margins", [
    fieldRow("top", page.margin_top, { type: "number", name: "page.margin_top" }),
    fieldRow("right", page.margin_right, { type: "number", name: "page.margin_right" }),
    fieldRow("bottom", page.margin_bottom, { type: "number", name: "page.margin_bottom" }),
    fieldRow("left", page.margin_left, { type: "number", name: "page.margin_left" })
  ], "field-grid"));
  fragment.appendChild(section("Background", [
    fieldRow("background", page.background_color || "#ffffff", {
      type: "color",
      name: "page.background_color",
      transparent: true
    }),
    fieldRow("transparent", Boolean(page.transparent), {
      type: "checkbox",
      name: "page.transparent"
    })
  ]));
  return fragment;
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
  if (input.name === "src") {
    setObjectSource(object, String(value));
    return;
  }
  if (input.name === "alt") {
    setObjectAlt(object, String(value));
    return;
  }
  if (input.name === "source_mode" || input.name === "maintain_aspect_ratio") {
    setObjectPropertyValue(object, input.name, inputValue(input, value));
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

function applyPageInput(template, input) {
  const value = inputValue(input, input.type === "checkbox" ? input.checked : input.value);
  if (input.name === "report_name") {
    template.metadata = template.metadata || {};
    template.metadata.name = String(value);
    template.metadata.title = String(value);
    return;
  }
  if (input.name === "page.size") {
    setPageSize(template, String(value));
    return;
  }
  if (input.name === "page.unit") {
    setPageUnit(template, String(value));
    return;
  }
  if (input.name === "page.orientation") {
    setPageOrientation(template, String(value));
    return;
  }
  if (input.name.startsWith("page.")) {
    const key = input.name.slice("page.".length);
    setPageValue(template, key, value);
  }
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

function shouldPreserveInspectorFocus(input) {
  if (!(input instanceof HTMLInputElement)) {
    return false;
  }
  return ["number", "text", "url"].includes(input.type);
}

function styleField(name, object, type, options = {}) {
  const style = objectStyle(object);
  return fieldRow(options.label || name, style[name] ?? defaultStyleValue(name), {
    type,
    name,
    styleKey: name,
    options: options.options,
    transparent: options.transparent,
    step: options.step,
    min: options.min,
    max: options.max
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
    if (options.accept) {
      input.accept = options.accept;
    }
    if (options.step !== undefined) {
      input.step = options.step;
    }
    if (options.min !== undefined) {
      input.min = options.min;
    }
    if (options.max !== undefined) {
      input.max = options.max;
    }
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

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(reader.error || new Error("Image upload failed")));
    reader.readAsDataURL(file);
  });
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
  if (name.startsWith("page.")) {
    button.dataset.styleKey = name;
    button.dataset.pageKey = name.slice("page.".length);
  } else {
    button.dataset.styleKey = name;
  }
  button.dataset.styleValue = "transparent";
  button.textContent = "transparent";
  button.title = "Use transparent background";
  return button;
}

function fontFamilyOptions() {
  return ["Arial", "Helvetica", "Times-Roman", "Courier"];
}

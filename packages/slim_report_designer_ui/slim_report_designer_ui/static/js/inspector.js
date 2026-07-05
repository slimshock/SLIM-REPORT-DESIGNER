import { icon } from "./icons.js";
import { fieldExists, getFieldValue, getRowValue, normalizeArrayFieldPath, normalizeFieldPath } from "./data_fields.js";
import {
  objectStyle,
  getBandById,
  setBandValue,
  setBandRepeatValue,
  setObjectAlt,
  setObjectBand,
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
  getSelectedObjects = () => [],
  getActiveBandId = () => "detail",
  getFields = () => [],
  getSampleData = () => ({}),
  onBeforeChange = () => {},
  onCommand = () => {},
  onSelectBand = () => {},
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
    if (input.name === "active_band") {
      onSelectBand(String(input.value));
      return;
    }
    const object = getSelectedObject();
    onBeforeChange("Edit properties");
    if (!object) {
      applyPageInput(getTemplate(), input, getActiveBandId());
      onChange({ preserveInspector: shouldPreserveInspectorFocus(input) });
      return;
    }
    applyInput(getTemplate(), object, input);
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
    const commandButton = event.target.closest("button[data-inspector-command]");
    if (commandButton) {
      event.preventDefault();
      onCommand(commandButton.dataset.inspectorCommand);
      return;
    }
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
      renderInspector(
        form,
        getSelectedObject(),
        getTemplate(),
        getSelectedObjects(),
        getActiveBandId(),
        getFields(),
        getSampleData()
      );
    }
  };
}

export function renderInspector(
  form,
  object,
  template = {},
  selectedObjects = [],
  activeBandId = "detail",
  fields = [],
  sampleData = {}
) {
  form.innerHTML = "";
  if (selectedObjects.length > 1) {
    form.appendChild(renderMultiSelectionInspector(selectedObjects));
    return;
  }
  if (!object) {
    form.appendChild(renderPageInspector(template, activeBandId, fields));
    return;
  }

  form.appendChild(section("Identity", [
    fieldRow("id", object.id, { disabled: true }),
    fieldRow("type", object.type, { disabled: true }),
    fieldRow("band", object.band || "detail", {
      type: "select",
      name: "band",
      options: bandOptions(template)
    })
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
    form.appendChild(section("Content", fieldContentFields(object, template, fields, sampleData)));
    form.appendChild(section("Style", textStyleFields(object)));
  } else if (object.type === "rectangle") {
    form.appendChild(section("Style", [
      styleField("border_width", object, "number"),
      styleField("border_color", object, "color"),
      styleField("border_radius", object, "number"),
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
  form.appendChild(section("Object State", [
    fieldRow("locked", Boolean(object.locked), { type: "checkbox", name: "locked" })
  ]));
}

function renderMultiSelectionInspector(objects) {
  const fragment = document.createDocumentFragment();
  const typeCounts = objects.reduce((counts, object) => {
    counts[object.type] = (counts[object.type] || 0) + 1;
    return counts;
  }, {});
  const summary = document.createElement("div");
  summary.className = "empty-state";
  summary.textContent = `${objects.length} objects selected: ${Object.entries(typeCounts)
    .map(([type, count]) => `${count} ${type}`)
    .join(", ")}`;
  fragment.appendChild(summary);
  fragment.appendChild(section("Align", [
    commandGrid([
      ["alignLeft", "Left"],
      ["alignCenter", "Center"],
      ["alignRight", "Right"],
      ["alignTop", "Top"],
      ["alignMiddle", "Middle"],
      ["alignBottom", "Bottom"]
    ])
  ]));
  fragment.appendChild(section("Distribute", [
    commandGrid([
      ["distributeHorizontal", "Horizontal"],
      ["distributeVertical", "Vertical"]
    ])
  ]));
  fragment.appendChild(section("Actions", [
    commandGrid([
      ["lockSelected", "Lock"],
      ["unlockSelected", "Unlock"],
      ["duplicate", "Duplicate"],
      ["delete", "Delete"]
    ])
  ]));
  return fragment;
}

function commandGrid(commands) {
  const row = document.createElement("div");
  row.className = "inspector-command-grid";
  for (const [command, label] of commands) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = command === "delete" ? "toolbar-button danger" : "toolbar-button";
    button.dataset.inspectorCommand = command;
    button.textContent = label;
    row.appendChild(button);
  }
  return row;
}

function renderPageInspector(template, activeBandId = "detail", fields = []) {
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
  fragment.appendChild(renderBandInspector(template, activeBandId, fields));
  return fragment;
}

function renderBandInspector(template, activeBandId = "detail", fields = []) {
  const band = getBandById(template, activeBandId) || template.bands?.[0] || {};
  const fragment = document.createDocumentFragment();
  fragment.appendChild(section("Band Properties", [
    fieldRow("active band", band.id || activeBandId, {
      type: "select",
      name: "active_band",
      options: bandOptions(template)
    }),
    fieldRow("band id", band.id || "", { disabled: true }),
    fieldRow("band type", band.type || "", { disabled: true }),
    fieldRow("band name", band.name || "", { name: "band.name" }),
    fieldRow("band y", band.y ?? 0, { type: "number", name: "band.y", disabled: true }),
    fieldRow("band height", band.height ?? 0, { type: "number", name: "band.height" }),
    fieldRow("band background", band.background_color || "transparent", {
      type: "color",
      name: "band.background_color"
    }),
    fieldRow("band visible", Boolean(band.visible ?? true), {
      type: "checkbox",
      name: "band.visible"
    }),
    fieldRow("band locked", Boolean(band.locked), {
      type: "checkbox",
      name: "band.locked"
    })
  ]));
  if (band.id === "detail") {
    fragment.appendChild(section("Repeating Detail", repeatFields(band, fields)));
  }
  return fragment;
}

function textStyleFields(object) {
  return [
    styleField("font_family", object, "select", { options: fontFamilyOptions() }),
    styleField("font_size", object, "number"),
    styleField("line_height", object, "number", { step: "0.1", min: "0.5" }),
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

function fieldContentFields(object, template, fields, sampleData) {
  const binding = normalizeFieldPath(object.binding || object.properties?.binding || "");
  const repeat = repeatForObject(template, object);
  const row = repeat?.array?.[0] || {};
  const rows = [
    fieldRow("binding", binding),
    fieldPickerRow(binding, fields),
    commandGrid([["chooseField", "Choose Field"]])
  ];
  const sampleValue = repeat ? getRowValue(row, binding, repeat.dataPath) : getFieldValue(sampleData, binding);
  const sample = document.createElement("p");
  sample.className = "field-sample-preview";
  sample.textContent = `Sample: ${
    sampleValue === undefined || sampleValue === null || sampleValue === ""
      ? "No sample value"
      : String(sampleValue)
  }`;
  rows.push(sample);
  if (repeat) {
    const note = document.createElement("p");
    note.className = "field-sample-preview";
    note.textContent = "This field is resolved per repeated row.";
    rows.push(note);
  }
  if (binding && !fieldExists(template, binding) && (!repeat || getRowValue(row, binding, repeat.dataPath) === "")) {
    const warning = document.createElement("p");
    warning.className = "field-warning";
    warning.textContent = "Binding not found in available fields.";
    rows.push(warning);
  }
  return rows;
}

function repeatFields(band, fields) {
  const repeat = band.repeat || {};
  return [
    fieldRow("repeat enabled", Boolean(repeat.enabled), {
      type: "checkbox",
      name: "band.repeat.enabled"
    }),
    fieldRow("data path", repeat.data_path || "", {
      type: "select",
      name: "band.repeat.data_path",
      options: arrayPathOptions(fields, repeat.data_path)
    }),
    fieldRow("row height", repeat.row_height || 22, {
      type: "number",
      name: "band.repeat.row_height",
      min: "8"
    }),
    fieldRow("preview rows", repeat.preview_rows || 10, {
      type: "number",
      name: "band.repeat.preview_rows",
      min: "1",
      max: "100"
    }),
    fieldRow("empty message", repeat.empty_message || "No records", {
      name: "band.repeat.empty_message"
    })
  ];
}

function arrayPathOptions(fields, current = "") {
  const paths = fields
    .map((field) => String(field.path || ""))
    .filter((path) => path.endsWith("[]"))
    .map(normalizeArrayFieldPath);
  const options = ["", ...new Set(paths)];
  if (current && !options.includes(current)) {
    options.push(current);
  }
  return options;
}

function fieldPickerRow(currentBinding, fields) {
  const options = ["", ...fields.map((field) => field.path)];
  const row = fieldRow("picker", currentBinding, {
    type: "select",
    name: "binding_picker",
    options
  });
  const select = row.querySelector("select");
  if (select && currentBinding && !options.includes(currentBinding)) {
    const option = document.createElement("option");
    option.value = currentBinding;
    option.textContent = currentBinding;
    select.appendChild(option);
    select.value = currentBinding;
  }
  return row;
}

function applyInput(template, object, input) {
  const value = input.type === "checkbox" ? input.checked : input.value;
  const numericFields = new Set(["x", "y", "width", "height"]);
  if (numericFields.has(input.name)) {
    object[input.name] = Number(value) || 0;
    return;
  }
  if (input.name === "locked") {
    object.locked = Boolean(value);
    object.properties = object.properties || {};
    object.properties.locked = object.locked;
    return;
  }
  if (input.dataset.styleKey) {
    setObjectStyleValue(object, input.dataset.styleKey, inputValue(input, value));
    return;
  }
  if (input.name === "band") {
    setObjectBand(template, object, String(value));
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
    setObjectBinding(object, normalizeFieldPath(value));
    return;
  }
  if (input.name === "binding_picker") {
    setObjectBinding(object, normalizeFieldPath(value));
    return;
  }
  object[input.name] = String(value);
}

function applyPageInput(template, input, activeBandId = "detail") {
  const value = inputValue(input, input.type === "checkbox" ? input.checked : input.value);
  if (input.name.startsWith("band.repeat.")) {
    const key = input.name.slice("band.repeat.".length);
    setBandRepeatValue(template, activeBandId, key, value);
    return;
  }
  if (input.name.startsWith("band.")) {
    setBandValue(template, activeBandId, input.name.slice("band.".length), value);
    return;
  }
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
  if (name === "line_height") {
    return 1.2;
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
  if (name === "border_radius") {
    return 0;
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

function bandOptions(template) {
  const bands = template.bands || [];
  if (bands.length === 0) {
    return ["detail"];
  }
  return bands.map((band) => band.id);
}

function repeatForObject(template, object) {
  const band = getBandById(template, object.band || object.band_id || "detail");
  const repeat = band?.id === "detail" && band.repeat?.enabled && band.repeat?.data_path ? band.repeat : null;
  if (!repeat) {
    return null;
  }
  const array = getFieldValue(template.data?.sample || {}, repeat.data_path);
  return {
    dataPath: repeat.data_path,
    array: Array.isArray(array) ? array : []
  };
}

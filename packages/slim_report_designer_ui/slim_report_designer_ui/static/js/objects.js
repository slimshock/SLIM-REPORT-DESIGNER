export function createDefaultTemplate() {
  return normalizeTemplate({
    version: "0.1",
    metadata: {
      name: "Untitled Report",
      title: "Untitled Report"
    },
    page: {
      size: "A4",
      orientation: "portrait",
      unit: "px",
      width: 595,
      height: 842,
      margin_top: 24,
      margin_right: 24,
      margin_bottom: 24,
      margin_left: 24,
      background_color: "#ffffff",
      transparent: false
    },
    objects: [],
    bands: [],
    assets: []
  });
}

export function normalizeTemplate(template) {
  const source = structuredClone(template || {});
  const title = source.metadata?.title || source.metadata?.name || "Untitled Report";
  source.version = String(source.version || "0.1");
  source.metadata = {
    ...(source.metadata || {}),
    name: source.metadata?.name || title,
    title
  };
  source.page = normalizePage(source.page || {});
  source.objects = Array.isArray(source.objects) ? source.objects.map(normalizeObject) : [];
  source.bands = Array.isArray(source.bands) ? source.bands : [];
  source.assets = Array.isArray(source.assets) ? source.assets : [];
  return source;
}

export function normalizeObject(object) {
  const type = object.type || "text";
  const normalized = {
    id: object.id || uniqueId(type, []),
    type,
    x: numberValue(object.x, 40),
    y: numberValue(object.y, 40),
    width: numberValue(object.width, 160),
    height: numberValue(object.height, defaultHeightForType(type)),
    properties: {
      ...(object.properties || {})
    }
  };

  if (object.text !== undefined) {
    normalized.text = String(object.text);
    normalized.properties.text = normalized.text;
  }
  if (object.binding !== undefined) {
    normalized.binding = String(object.binding);
    normalized.properties.binding = normalized.binding;
  }
  const source = object.src ?? object.source ?? object.properties?.src ?? object.properties?.source;
  if (type === "image") {
    normalized.src = source === undefined ? "" : String(source);
    normalized.alt = String(object.alt ?? object.properties?.alt ?? "");
    normalized.properties.src = normalized.src;
    normalized.properties.source = normalized.src;
    normalized.properties.alt = normalized.alt;
    normalized.properties.maintain_aspect_ratio = Boolean(
      object.maintain_aspect_ratio ?? object.properties?.maintain_aspect_ratio ?? true
    );
  }
  const style = explicitStyle(object);
  if (Object.keys(style).length > 0) {
    normalized.style = style;
    normalized.properties.style = style;
  } else if (normalized.properties.style) {
    delete normalized.properties.style;
  }
  return normalized;
}

export function createObject(type, template) {
  const ids = template.objects.map((object) => object.id);
  const base = {
    id: uniqueId(type, ids),
    type,
    x: 60,
    y: 60,
    width: 160,
    height: 32,
    properties: {
      style: {}
    }
  };

  if (type === "text") {
    base.text = "Text";
    base.properties.text = base.text;
    base.properties.style = { font_size: 14 };
  } else if (type === "field") {
    base.binding = "patient.name";
    base.properties.binding = base.binding;
    base.properties.style = { font_size: 14 };
  } else if (type === "line") {
    base.width = 220;
    base.height = 0;
    base.properties.style = { stroke_width: 1 };
  } else if (type === "rectangle") {
    base.width = 180;
    base.height = 90;
    base.properties.style = { border_width: 1 };
  } else if (type === "image") {
    base.x = 40;
    base.y = 40;
    base.width = 120;
    base.height = 80;
    base.src = "";
    base.alt = "";
    base.properties.src = "";
    base.properties.source = "";
    base.properties.alt = "";
    base.properties.maintain_aspect_ratio = true;
    base.properties.style = defaultStyleForType("image");
  }

  return normalizeObject(base);
}

export function duplicateObject(object, template) {
  const clone = normalizeObject(structuredClone(object));
  clone.id = uniqueId(`${object.type}_copy`, template.objects.map((item) => item.id));
  clone.x += 20;
  clone.y += 20;
  return clone;
}

export function objectStyle(object) {
  return {
    ...defaultStyleForType(object?.type),
    ...explicitStyle(object || {})
  };
}

export function setObjectStyleValue(object, key, value) {
  object.properties = object.properties || {};
  object.properties.style = object.properties.style || {};
  object.properties.style[key] = value;
  object.style = {
    ...(object.style || {}),
    [key]: value
  };
}

export function defaultStyleForType(type) {
  if (type === "rectangle") {
    return {
      border_width: 1,
      border_color: "#111827",
      background_color: "transparent"
    };
  }
  if (type === "line") {
    return {
      stroke_width: 1,
      stroke_color: "#111827"
    };
  }
  if (type === "image") {
    return {
      object_fit: "contain",
      opacity: 1,
      border_radius: 0,
      border_width: 0,
      border_color: "#000000",
      background_color: "transparent"
    };
  }
  return {
    font_family: "Arial",
    font_size: 12,
    bold: false,
    italic: false,
    underline: false,
    color: "#111827",
    background_color: "transparent",
    align: "left",
    vertical_align: "top"
  };
}

export function setObjectText(object, value) {
  object.text = value;
  object.properties = object.properties || {};
  object.properties.text = value;
}

export function setObjectBinding(object, value) {
  object.binding = value;
  object.properties = object.properties || {};
  object.properties.binding = value;
}

export function setObjectSource(object, value) {
  object.src = value;
  object.properties = object.properties || {};
  object.properties.src = value;
  object.properties.source = value;
}

export function setObjectAlt(object, value) {
  object.alt = value;
  object.properties = object.properties || {};
  object.properties.alt = value;
}

export function setObjectPropertyValue(object, key, value) {
  object.properties = object.properties || {};
  object.properties[key] = value;
}

export function setPageValue(template, key, value) {
  template.page = normalizePage({
    ...(template.page || {}),
    [key]: value
  });
}

export function setPageSize(template, size) {
  const page = normalizePage({ ...(template.page || {}), size });
  if (size !== "Custom") {
    const dimensions = paperDimensions(size, page.unit, page.orientation);
    page.width = dimensions.width;
    page.height = dimensions.height;
  }
  template.page = page;
}

export function setPageUnit(template, unit) {
  const current = normalizePage(template.page || {});
  const page = normalizePage({ ...current, unit });
  if (page.size !== "Custom") {
    const dimensions = paperDimensions(page.size, unit, page.orientation);
    page.width = dimensions.width;
    page.height = dimensions.height;
  }
  template.page = page;
}

export function setPageOrientation(template, orientation) {
  const page = normalizePage({ ...(template.page || {}), orientation });
  if (page.size !== "Custom") {
    const dimensions = paperDimensions(page.size, page.unit, orientation);
    page.width = dimensions.width;
    page.height = dimensions.height;
  } else if (
    (orientation === "landscape" && page.width < page.height) ||
    (orientation === "portrait" && page.width > page.height)
  ) {
    [page.width, page.height] = [page.height, page.width];
  }
  template.page = page;
}

export function templateTitle(template) {
  return template.metadata?.title || template.metadata?.name || "Untitled Report";
}

export function uniqueId(prefix, existingIds) {
  const safePrefix = String(prefix || "object").toLowerCase().replace(/[^a-z0-9]+/g, "_");
  let index = 1;
  let candidate = `${safePrefix}_${index}`;
  while (existingIds.includes(candidate)) {
    index += 1;
    candidate = `${safePrefix}_${index}`;
  }
  return candidate;
}

function numberValue(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function normalizePage(page) {
  const size = page.size || "A4";
  const orientation = page.orientation === "landscape" ? "landscape" : "portrait";
  const unit = ["px", "mm", "in"].includes(page.unit) ? page.unit : "px";
  const fallback = paperDimensions(size, unit, orientation);
  return {
    size,
    orientation,
    unit,
    width: numberValue(page.width, fallback.width),
    height: numberValue(page.height, fallback.height),
    margin_top: numberValue(page.margin_top ?? page.margin?.top, unit === "px" ? 24 : unit === "mm" ? 10 : 0.4),
    margin_right: numberValue(page.margin_right ?? page.margin?.right, unit === "px" ? 24 : unit === "mm" ? 10 : 0.4),
    margin_bottom: numberValue(page.margin_bottom ?? page.margin?.bottom, unit === "px" ? 24 : unit === "mm" ? 10 : 0.4),
    margin_left: numberValue(page.margin_left ?? page.margin?.left, unit === "px" ? 24 : unit === "mm" ? 10 : 0.4),
    background_color: String(page.background_color || "#ffffff"),
    transparent: Boolean(page.transparent)
  };
}

export function paperDimensions(size, unit, orientation) {
  const key = String(size || "A4").toLowerCase();
  const table = {
    a4: { px: [595, 842], mm: [210, 297], in: [8.27, 11.69] },
    letter: { px: [612, 792], mm: [215.9, 279.4], in: [8.5, 11] },
    legal: { px: [612, 1008], mm: [215.9, 355.6], in: [8.5, 14] },
    custom: { px: [595, 842], mm: [210, 297], in: [8.27, 11.69] }
  };
  const values = table[key]?.[unit] || table.a4.px;
  let [width, height] = values;
  if (orientation === "landscape" && width < height) {
    [width, height] = [height, width];
  }
  if (orientation === "portrait" && width > height) {
    [width, height] = [height, width];
  }
  return { width, height };
}

function defaultHeightForType(type) {
  if (type === "line") {
    return 0;
  }
  if (type === "image") {
    return 80;
  }
  return 32;
}

function explicitStyle(object) {
  const properties = object.properties || {};
  const style = {
    ...(properties.style || {}),
    ...(object.style || {})
  };

  for (const key of [
    "align",
    "background_color",
    "bold",
    "border_color",
    "border_width",
    "color",
    "fill_color",
    "font_family",
    "font_size",
    "italic",
    "line_width",
    "object_fit",
    "opacity",
    "border_radius",
    "stroke_color",
    "stroke_width",
    "underline",
    "vertical_align"
  ]) {
    if (properties[key] !== undefined && style[key] === undefined) {
      style[key] = properties[key];
    }
  }

  if (style.fill_color !== undefined && style.background_color === undefined) {
    style.background_color = style.fill_color;
  }
  if (style.line_width !== undefined && style.stroke_width === undefined) {
    style.stroke_width = style.line_width;
  }
  if (style.border_color !== undefined && style.stroke_color === undefined && object.type === "line") {
    style.stroke_color = style.border_color;
  }
  return style;
}

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
      width: 595,
      height: 842
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
  source.page = {
    size: "A4",
    orientation: "portrait",
    width: 595,
    height: 842,
    ...(source.page || {})
  };
  source.page.unit = "px";
  source.objects = Array.isArray(source.objects) ? source.objects.map(normalizeObject) : [];
  source.bands = Array.isArray(source.bands) ? source.bands : [];
  source.assets = Array.isArray(source.assets) ? source.assets : [];
  return source;
}

export function normalizeObject(object) {
  const normalized = {
    id: object.id || uniqueId(object.type || "object", []),
    type: object.type || "text",
    x: numberValue(object.x, 40),
    y: numberValue(object.y, 40),
    width: numberValue(object.width, 160),
    height: numberValue(object.height, object.type === "line" ? 0 : 32),
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
  if (object.style || object.properties?.style) {
    normalized.style = {
      ...(object.properties?.style || {}),
      ...(object.style || {})
    };
    normalized.properties.style = normalized.style;
  }
  if (!normalized.style) {
    normalized.style = {};
    normalized.properties.style = normalized.style;
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
    base.properties.style = { font_size: 14, bold: false };
  } else if (type === "field") {
    base.binding = "patient.name";
    base.properties.binding = base.binding;
    base.properties.style = { font_size: 14, bold: false };
  } else if (type === "line") {
    base.width = 220;
    base.height = 0;
    base.properties.style = { stroke_width: 1 };
  } else if (type === "rectangle") {
    base.width = 180;
    base.height = 90;
    base.properties.style = { border_width: 1 };
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
  object.properties = object.properties || {};
  object.properties.style = object.properties.style || {};
  object.style = object.properties.style;
  return object.properties.style;
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

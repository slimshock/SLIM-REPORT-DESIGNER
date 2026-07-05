export function normalizeFieldPath(path) {
  return String(path || "")
    .trim()
    .replace(/^\{\{\s*/, "")
    .replace(/\s*\}\}$/, "")
    .replace(/\s*\.\s*/g, ".")
    .replace(/\s+/g, "");
}

export function flattenDataPaths(sampleData) {
  const paths = [];
  walkValue(sampleData, "", paths);
  return [...new Set(paths)].filter(Boolean);
}

export function inferFieldsFromSample(sampleData) {
  return flattenDataPaths(sampleData).map((path) => {
    const sample = getFieldValue(sampleData, path);
    return {
      path,
      label: labelForPath(path),
      type: typeForValue(sample),
      sample: sample === undefined || sample === null ? "" : String(sample)
    };
  });
}

export function getFieldValue(sampleData, path) {
  const normalized = normalizeFieldPath(path);
  if (!normalized) {
    return undefined;
  }
  let value = sampleData;
  for (const token of pathTokens(normalized)) {
    if (value === undefined || value === null) {
      return undefined;
    }
    if (token === "[]") {
      value = Array.isArray(value) ? value[0] : undefined;
    } else if (/^\[\d+\]$/.test(token)) {
      const index = Number(token.slice(1, -1));
      value = Array.isArray(value) ? value[index] : undefined;
    } else {
      value = value[token];
    }
  }
  return value;
}

export function fieldExists(template, path) {
  const normalized = normalizeFieldPath(path);
  if (!normalized) {
    return false;
  }
  return getTemplateFields(template).some((field) => normalizeFieldPath(field.path) === normalized);
}

export function getTemplateFields(template) {
  const data = template?.data;
  const explicitFields = Array.isArray(data?.fields) ? data.fields : [];
  if (explicitFields.length > 0) {
    return explicitFields
      .map((field) => normalizeField(field, data?.sample))
      .filter((field) => field.path);
  }
  if (data?.sample && typeof data.sample === "object") {
    return inferFieldsFromSample(data.sample);
  }
  return [];
}

export function normalizeDataMetadata(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return undefined;
  }
  const normalized = { ...data };
  if (Array.isArray(data.fields)) {
    normalized.fields = data.fields
      .map((field) => normalizeField(field, data.sample))
      .filter((field) => field.path);
  } else if (data.sample && typeof data.sample === "object") {
    normalized.fields = inferFieldsFromSample(data.sample);
  }
  return normalized;
}

function normalizeField(field, sampleData) {
  const path = normalizeFieldPath(typeof field === "string" ? field : field?.path);
  const sample = field?.sample ?? getFieldValue(sampleData, path);
  return {
    path,
    label: String(field?.label || labelForPath(path)),
    type: String(field?.type || typeForValue(sample)),
    sample: sample === undefined || sample === null ? "" : String(sample)
  };
}

function walkValue(value, prefix, paths) {
  if (Array.isArray(value)) {
    if (!prefix) {
      value.slice(0, 1).forEach((item) => walkValue(item, "", paths));
      return;
    }
    if (value.length === 0) {
      paths.push(`${prefix}[]`);
      return;
    }
    const first = value[0];
    if (isPlainObject(first) || Array.isArray(first)) {
      walkValue(first, `${prefix}[0]`, paths);
      walkValue(first, `${prefix}[]`, paths);
    } else {
      paths.push(`${prefix}[0]`, `${prefix}[]`);
    }
    return;
  }
  if (isPlainObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      const nextPath = prefix ? `${prefix}.${key}` : key;
      walkValue(item, nextPath, paths);
    }
    return;
  }
  if (prefix) {
    paths.push(prefix);
  }
}

function pathTokens(path) {
  const tokens = [];
  for (const part of path.split(".")) {
    const name = part.replace(/\[(?:\d+)?\]/g, "");
    if (name) {
      tokens.push(name);
    }
    for (const match of part.matchAll(/\[(\d*)\]/g)) {
      tokens.push(match[1] === "" ? "[]" : `[${match[1]}]`);
    }
  }
  return tokens;
}

function labelForPath(path) {
  const clean = normalizeFieldPath(path).split(".").pop()?.replace(/\[(?:\d+)?\]/g, "") || "Field";
  return clean
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function typeForValue(value) {
  if (Array.isArray(value)) {
    return "array";
  }
  if (value === null) {
    return "null";
  }
  return typeof value === "object" ? "object" : typeof value;
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

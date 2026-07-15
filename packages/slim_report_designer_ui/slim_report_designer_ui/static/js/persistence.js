const FORBIDDEN_KEYS = new Set([
  "password",
  "runtimepassword",
  "resolvedpassword",
  "parametervalues",
  "runtimevalues",
  "previewhtml",
  "connectionobject",
  "cursorobject",
  "connectiontestresult",
  "readonlyverificationresult",
  "latesterror",
  "loadingstate",
  "previewstate"
]);

let reportSessionKey = "";

export function safeTemplateSnapshot(template) {
  return sanitize(structuredClone(template || {}));
}

export function currentReportSessionKey() {
  if (!reportSessionKey) {
    reportSessionKey = createSessionKey();
  }
  return reportSessionKey;
}

export function rotateReportSessionKey() {
  reportSessionKey = createSessionKey();
  return reportSessionKey;
}

function sanitize(value) {
  if (Array.isArray(value)) {
    return value.map(sanitize);
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  const result = {};
  for (const [key, child] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.has(key.replaceAll("_", "").toLowerCase())) {
      continue;
    }
    result[key] = sanitize(child);
  }
  return result;
}

function createSessionKey() {
  const cryptoApi = globalThis.crypto || globalThis.window?.crypto;
  if (cryptoApi?.randomUUID) {
    return cryptoApi.randomUUID();
  }
  if (cryptoApi?.getRandomValues) {
    const bytes = new Uint8Array(24);
    cryptoApi.getRandomValues(bytes);
    return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  }
  return `${Date.now().toString(36)}-${Array.from(
    { length: 6 }, () => Math.random().toString(36).slice(2)
  ).join("")}`;
}

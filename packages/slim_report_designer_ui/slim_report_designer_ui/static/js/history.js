import { safeTemplateSnapshot } from "./persistence.js";

const MAX_VERSIONS = 20;

export function getHistoryKey(templateId) {
  return `slim_report_designer.history.${safeTemplateId(templateId)}`;
}

export function listVersions(templateId) {
  return readVersions(templateId);
}

export function createVersion(templateId, template, label) {
  const versions = readVersions(templateId);
  const version = {
    id: uniqueVersionId(),
    created_at: new Date().toISOString(),
    label: label || "Version",
    object_count: Array.isArray(template?.objects) ? template.objects.length : 0,
    template: safeTemplateSnapshot(template)
  };
  versions.unshift(version);
  writeVersions(templateId, versions.slice(0, MAX_VERSIONS));
  return version;
}

export function restoreVersion(templateId, versionId) {
  const version = readVersions(templateId).find((item) => item.id === versionId);
  return version ? safeTemplateSnapshot(version.template) : null;
}

export function deleteVersion(templateId, versionId) {
  writeVersions(templateId, readVersions(templateId).filter((item) => item.id !== versionId));
}

export function clearVersions(templateId) {
  localStorage.removeItem(getHistoryKey(templateId));
}

function readVersions(templateId) {
  try {
    const payload = JSON.parse(localStorage.getItem(getHistoryKey(templateId)) || "[]");
    if (!Array.isArray(payload)) {
      return [];
    }
    const sanitized = payload.map((version) => ({
      ...version,
      template: safeTemplateSnapshot(version.template)
    }));
    localStorage.setItem(getHistoryKey(templateId), JSON.stringify(sanitized));
    return sanitized;
  } catch (error) {
    return [];
  }
}

function writeVersions(templateId, versions) {
  localStorage.setItem(getHistoryKey(templateId), JSON.stringify(versions));
}

function safeTemplateId(templateId) {
  return String(templateId || "default").trim().replace(/[^a-zA-Z0-9_.-]+/g, "_") || "default";
}

function uniqueVersionId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

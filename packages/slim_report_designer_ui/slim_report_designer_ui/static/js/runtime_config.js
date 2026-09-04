export function runtimeConfig() {
  const legacyConfig = window.SLIM_REPORT_CONFIG || {};

  return {
    apiBase:
      legacyConfig.apiBase || metaContent("slim-report-api-base"),

    templateId:
      legacyConfig.templateId || metaContent("slim-report-template-id"),

    canSave:
      typeof legacyConfig.canSave === "boolean"
        ? legacyConfig.canSave
        : metaBoolean("slim-report-can-save"),

    saveEnabled:
      typeof legacyConfig.saveEnabled === "boolean"
        ? legacyConfig.saveEnabled
        : metaBoolean("slim-report-save-enabled"),

    databaseDataSourcesEnabled:
      typeof legacyConfig.databaseDataSourcesEnabled === "boolean"
        ? legacyConfig.databaseDataSourcesEnabled
        : metaBoolean("slim-report-feature-database-data-sources") ?? true,

    sqlDatasetsEnabled:
      typeof legacyConfig.sqlDatasetsEnabled === "boolean"
        ? legacyConfig.sqlDatasetsEnabled
        : metaBoolean("slim-report-feature-sql-datasets") ?? true,

    csrfHeaderName:
      legacyConfig.csrfHeaderName ||
      metaContent("slim-report-csrf-header"),

    csrfToken:
      legacyConfig.csrfToken ||
      metaContent("slim-report-csrf-token"),

    brandName:
      legacyConfig.brandName ||
      metaContent("slim-report-brand-name"),

    brandMark:
      legacyConfig.brandMark ||
      metaContent("slim-report-brand-mark"),

    pageTitle:
      legacyConfig.pageTitle ||
      metaContent("slim-report-page-title"),

    backUrl:
      legacyConfig.backUrl ||
      metaContent("slim-report-back-url"),

    backLabel:
      legacyConfig.backLabel ||
      metaContent("slim-report-back-label")
  };
}

function metaContent(name) {
  return document.querySelector(`meta[name="${name}"]`)?.content || "";
}

function metaBoolean(name) {
  const value = metaContent(name).toLowerCase();

  if (value === "true") {
    return true;
  }

  if (value === "false") {
    return false;
  }

  return undefined;
}
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
  return getValueByPath(sampleData, path);
}

export function resolveBinding(binding, sampleData = {}, context = {}) {
  const path = normalizeFieldPath(binding);
  if (!path) {
    return "";
  }
  const systemValue = resolveSystemBinding(path, context);
  if (systemValue !== undefined) {
    return systemValue;
  }
  const groupValue = resolveGroupBinding(path, context);
  if (groupValue !== undefined) {
    return groupValue;
  }
  const reportValue = resolveReportBinding(path, sampleData);
  if (reportValue !== undefined) {
    return reportValue;
  }
  if (context.rowData) {
    const rowValue = getRowValue(context.rowData, path, context.repeatDataPath || "");
    if (rowValue !== "") {
      return rowValue;
    }
  }
  const value = getFieldValue(sampleData, path);
  return value === undefined || value === null ? "" : value;
}

export function evaluateFormula(formula, sampleData = {}, context = {}) {
  const source = String(formula || "").trim();
  if (!source) {
    return { value: "", error: "" };
  }
  try {
    const parser = new FormulaParser(tokenizeFormula(source), sampleData, context);
    const value = parser.parse();
    return { value, error: "" };
  } catch (error) {
    return { value: "", error: error instanceof Error ? error.message : String(error) };
  }
}

export function resolveFormula(formula, sampleData = {}, context = {}) {
  return evaluateFormula(formula, sampleData, context).value;
}

export function evaluateCondition(condition, sampleData = {}, context = {}) {
  const result = evaluateFormula(condition, sampleData, context);
  return !result.error && formulaTruthy(result.value);
}

export function conditionalStyleResult(object, baseStyle = {}, sampleData = {}, context = {}) {
  let style = { ...(baseStyle || {}) };
  let hidden = false;
  for (const rule of conditionRules(object)) {
    if (rule.enabled === false || !String(rule.condition || "").trim()) {
      continue;
    }
    if (!evaluateCondition(rule.condition, sampleData, context)) {
      continue;
    }
    if (rule.style && typeof rule.style === "object" && !Array.isArray(rule.style)) {
      style = { ...style, ...rule.style };
    }
    const action = typeof rule.action === "object"
      ? rule.action?.type || rule.action?.name || ""
      : rule.action || "";
    if (String(action).toLowerCase() === "hide") {
      hidden = true;
    }
  }
  return { style, hidden };
}

export function resolveSystemBinding(path, context = {}) {
  if (path === "page.number") {
    return context.pageNumber ?? 1;
  }
  if (path === "page.index") {
    return context.pageIndex ?? Math.max((context.pageNumber ?? 1) - 1, 0);
  }
  if (path === "page.total_pages" || path === "page.count") {
    return context.totalPages ?? 1;
  }
  if (path === "date.today") {
    return formatDate(new Date());
  }
  if (path === "datetime.now") {
    return formatDateTime(new Date());
  }
  return undefined;
}

function tokenizeFormula(source) {
  const tokens = [];
  let index = 0;
  while (index < source.length) {
    const char = source[index];
    if (/\s/.test(char)) {
      index += 1;
      continue;
    }
    if (char === "'" || char === "\"") {
      const quote = char;
      let value = "";
      index += 1;
      while (index < source.length && source[index] !== quote) {
        if (source[index] === "\\" && index + 1 < source.length) {
          value += source[index + 1];
          index += 2;
        } else {
          value += source[index];
          index += 1;
        }
      }
      if (source[index] !== quote) {
        throw new Error("Unterminated string literal");
      }
      tokens.push({ type: "string", value });
      index += 1;
      continue;
    }
    if (/\d/.test(char) || (char === "." && /\d/.test(source[index + 1] || ""))) {
      let raw = char;
      index += 1;
      while (index < source.length && /[\d.]/.test(source[index])) {
        raw += source[index];
        index += 1;
      }
      const value = Number(raw);
      if (!Number.isFinite(value)) {
        throw new Error("Invalid number literal");
      }
      tokens.push({ type: "number", value });
      continue;
    }
    const two = source.slice(index, index + 2);
    if (["==", "!=", ">=", "<="].includes(two)) {
      tokens.push({ type: "operator", value: two });
      index += 2;
      continue;
    }
    if ("+-*/%><(),".includes(char)) {
      tokens.push({ type: "operator", value: char });
      index += 1;
      continue;
    }
    if (/[A-Za-z_]/.test(char)) {
      let value = char;
      index += 1;
      while (index < source.length && /[A-Za-z0-9_.]/.test(source[index])) {
        value += source[index];
        index += 1;
      }
      tokens.push({ type: "identifier", value });
      continue;
    }
    throw new Error(`Unsupported token: ${char}`);
  }
  tokens.push({ type: "eof", value: "" });
  return tokens;
}

class FormulaParser {
  constructor(tokens, sampleData, context) {
    this.tokens = tokens;
    this.sampleData = sampleData || {};
    this.context = context || {};
    this.index = 0;
  }

  parse() {
    const value = this.logicalOr();
    this.expect("eof");
    return value;
  }

  logicalOr() {
    let left = this.logicalAnd();
    while (this.matchIdentifierValue("or")) {
      const right = this.logicalAnd();
      left = formulaTruthy(left) || formulaTruthy(right);
    }
    return left;
  }

  logicalAnd() {
    let left = this.logicalNot();
    while (this.matchIdentifierValue("and")) {
      const right = this.logicalNot();
      left = formulaTruthy(left) && formulaTruthy(right);
    }
    return left;
  }

  logicalNot() {
    if (this.matchIdentifierValue("not")) {
      return !formulaTruthy(this.logicalNot());
    }
    return this.comparison();
  }

  comparison() {
    let left = this.additive();
    while (this.matchOperator(["==", "!=", ">", ">=", "<", "<="])) {
      const operator = this.previous().value;
      const right = this.additive();
      left = compareFormulaValues(left, right, operator);
    }
    return left;
  }

  additive() {
    let left = this.multiplicative();
    while (this.matchOperator(["+", "-"])) {
      const operator = this.previous().value;
      const right = this.multiplicative();
      left = operator === "+" ? addFormulaValues(left, right) : numericFormulaValues(left, right, (a, b) => a - b);
    }
    return left;
  }

  multiplicative() {
    let left = this.unary();
    while (this.matchOperator(["*", "/", "%"])) {
      const operator = this.previous().value;
      const right = this.unary();
      if (operator === "*") {
        left = numericFormulaValues(left, right, (a, b) => a * b);
      } else if (operator === "/") {
        left = numericFormulaValues(left, right, (a, b) => {
          if (b === 0) {
            throw new Error("Division by zero");
          }
          return a / b;
        });
      } else {
        left = numericFormulaValues(left, right, (a, b) => {
          if (b === 0) {
            throw new Error("Modulo by zero");
          }
          return a % b;
        });
      }
    }
    return left;
  }

  unary() {
    if (this.matchOperator(["-", "+"])) {
      const operator = this.previous().value;
      const value = formulaNumber(this.unary());
      if (value === null) {
        throw new Error("Unary operator requires a number");
      }
      return operator === "-" ? -value : value;
    }
    return this.primary();
  }

  primary() {
    if (this.match("number") || this.match("string")) {
      return this.previous().value;
    }
    if (this.match("identifier")) {
      const identifier = this.previous().value;
      if (identifier === "true") {
        return true;
      }
      if (identifier === "false") {
        return false;
      }
      if (identifier === "null") {
        return null;
      }
      if (this.matchOperator(["("])) {
        return this.call(identifier);
      }
      return resolveBinding(identifier, this.sampleData, this.context);
    }
    if (this.matchOperator(["("])) {
      const value = this.comparison();
      this.expectOperator(")");
      return value;
    }
    throw new Error("Expected formula expression");
  }

  call(name) {
    const args = [];
    if (!this.checkOperator(")")) {
      do {
        args.push(this.logicalOr());
      } while (this.matchOperator([","]));
    }
    this.expectOperator(")");
    return callFormulaFunction(name, args);
  }

  match(type) {
    if (!this.check(type)) {
      return false;
    }
    this.index += 1;
    return true;
  }

  matchOperator(values) {
    if (this.peek().type !== "operator" || !values.includes(this.peek().value)) {
      return false;
    }
    this.index += 1;
    return true;
  }

  matchIdentifierValue(value) {
    if (this.peek().type !== "identifier" || this.peek().value !== value) {
      return false;
    }
    this.index += 1;
    return true;
  }

  check(type) {
    return this.peek().type === type;
  }

  checkOperator(value) {
    return this.peek().type === "operator" && this.peek().value === value;
  }

  expect(type) {
    if (!this.match(type)) {
      throw new Error(`Expected ${type}`);
    }
  }

  expectOperator(value) {
    if (!this.matchOperator([value])) {
      throw new Error(`Expected ${value}`);
    }
  }

  peek() {
    return this.tokens[this.index] || { type: "eof", value: "" };
  }

  previous() {
    return this.tokens[this.index - 1] || { type: "eof", value: "" };
  }
}

function callFormulaFunction(name, args) {
  const functions = {
    concat: (...values) => values.map(formulaText).join(""),
    upper: (value = "") => formulaText(value).toUpperCase(),
    lower: (value = "") => formulaText(value).toLowerCase(),
    title: (value = "") => formulaText(value).replace(/\w\S*/g, (part) => part[0].toUpperCase() + part.slice(1).toLowerCase()),
    trim: (value = "") => formulaText(value).trim(),
    number: (value, decimals = 0) => {
      const number = formulaNumber(value);
      const places = formulaNumber(decimals);
      if (number === null || places === null) {
        return "";
      }
      return number.toFixed(Math.max(0, Math.min(Number.parseInt(places, 10) || 0, 10)));
    },
    default: (value, fallback = "") => value === "" || value === null || value === undefined ? fallback : value,
    if: (condition, trueValue = "", falseValue = "") => formulaTruthy(condition) ? trueValue : falseValue,
    contains: (value, text) => formulaText(value).includes(formulaText(text)),
    starts_with: (value, text) => formulaText(value).startsWith(formulaText(text)),
    ends_with: (value, text) => formulaText(value).endsWith(formulaText(text))
  };
  const fn = functions[name];
  if (!fn) {
    throw new Error(`Unsupported function: ${name}`);
  }
  return fn(...args);
}

function addFormulaValues(left, right) {
  const leftNumber = formulaNumber(left);
  const rightNumber = formulaNumber(right);
  if (leftNumber !== null && rightNumber !== null) {
    return normalizeFormulaNumber(leftNumber + rightNumber);
  }
  return `${formulaText(left)}${formulaText(right)}`;
}

function numericFormulaValues(left, right, operation) {
  const leftNumber = formulaNumber(left);
  const rightNumber = formulaNumber(right);
  if (leftNumber === null || rightNumber === null) {
    throw new Error("Operator requires numbers");
  }
  return normalizeFormulaNumber(operation(leftNumber, rightNumber));
}

function compareFormulaValues(left, right, operator) {
  if (operator === "==") {
    return left === right;
  }
  if (operator === "!=") {
    return left !== right;
  }
  const leftNumber = formulaNumber(left);
  const rightNumber = formulaNumber(right);
  const a = leftNumber !== null && rightNumber !== null ? leftNumber : formulaText(left);
  const b = leftNumber !== null && rightNumber !== null ? rightNumber : formulaText(right);
  if (operator === ">") {
    return a > b;
  }
  if (operator === ">=") {
    return a >= b;
  }
  if (operator === "<") {
    return a < b;
  }
  if (operator === "<=") {
    return a <= b;
  }
  throw new Error("Unsupported comparison");
}

function formulaNumber(value) {
  if (typeof value === "boolean" || value === null || value === undefined) {
    return null;
  }
  const number = Number(String(value).replace(/,/g, "").trim());
  return Number.isFinite(number) ? number : null;
}

function normalizeFormulaNumber(value) {
  return Number.isInteger(value) ? Number.parseInt(value, 10) : value;
}

function formulaTruthy(value) {
  if (value === "" || value === null || value === undefined || value === false) {
    return false;
  }
  if (typeof value === "string" && ["false", "0", "no"].includes(value.trim().toLowerCase())) {
    return false;
  }
  return Boolean(value);
}

function formulaText(value) {
  return value === null || value === undefined ? "" : String(value);
}

function conditionRules(object) {
  const source = object?.conditions ?? object?.properties?.conditions;
  return Array.isArray(source) ? source : [];
}

export function resolveGroupBinding(path, context = {}) {
  const group = context.groupData;
  if (!group) {
    return undefined;
  }
  const field = String(group.field || "");
  const rows = Array.isArray(group.rows) ? group.rows : [];
  if ([field, "group", "group.key", "group.value"].includes(path)) {
    return group.key ?? "";
  }
  if (path === "group.field") {
    return field;
  }
  if (path === "group.count") {
    return aggregateCount(rows);
  }
  const match = path.match(/^group\.(sum|avg|min|max)\.(.+)$/);
  if (!match) {
    return undefined;
  }
  return aggregateRows(rows, match[1], match[2]);
}

export function resolveReportBinding(path, sampleData = {}) {
  const match = path.match(/^report\.(count|sum|avg|min|max)\.(.+)$/);
  if (!match) {
    return undefined;
  }
  const [, operation, target] = match;
  if (operation === "count") {
    return aggregateCount(getArrayByPath(sampleData, target));
  }
  const { arrayPath, field } = splitReportAggregatePath(sampleData, target);
  if (!arrayPath || !field) {
    return "";
  }
  const rows = getArrayByPath(sampleData, arrayPath);
  if (rows.length === 0 && getValueByPath(sampleData, arrayPath) === undefined) {
    return "";
  }
  return aggregateRows(rows, operation, field);
}

export function getValueByPath(data, path) {
  const normalized = normalizeFieldPath(path);
  if (!normalized) {
    return undefined;
  }
  let value = data;
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

export function getArrayByPath(data, path) {
  const value = getValueByPath(data, normalizeArrayFieldPath(path));
  return Array.isArray(value) ? value : [];
}

export function getArrayChildFields(template, dataPath) {
  const arrayPath = normalizeArrayFieldPath(dataPath);
  if (!arrayPath) {
    return [];
  }
  const prefix = `${arrayPath}[].`;
  return getTemplateFields(template)
    .filter((field) => normalizeFieldPath(field.path).startsWith(prefix))
    .map((field) => ({
      ...field,
      child_path: normalizeFieldPath(field.path).slice(prefix.length)
    }))
    .filter((field) => field.child_path);
}

export function getRowValue(row, binding, repeatDataPath = "") {
  const normalized = normalizeFieldPath(binding);
  if (!normalized) {
    return "";
  }
  const repeatPath = normalizeArrayFieldPath(repeatDataPath);
  let rowPath = normalized;
  const arrayPrefix = repeatPath ? `${repeatPath}[]` : "";
  if (arrayPrefix && normalized.startsWith(`${arrayPrefix}.`)) {
    rowPath = normalized.slice(arrayPrefix.length + 1);
  } else if (repeatPath && normalized.startsWith(`${repeatPath}[].`)) {
    rowPath = normalized.slice(`${repeatPath}[].`.length);
  }
  const value = getValueByPath(row, rowPath);
  return value === undefined || value === null ? "" : value;
}

export function normalizeArrayFieldPath(path) {
  return normalizeFieldPath(path).replace(/\[(?:\d+)?\]/g, "");
}

export function isArrayFieldPath(path) {
  return /\[(?:\d*)\]/.test(normalizeFieldPath(path));
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
  let fields = [];
  if (explicitFields.length > 0) {
    fields = explicitFields
      .map((field) => normalizeField(field, data?.sample))
      .filter((field) => field.path);
    return withVirtualFields(template, fields);
  }
  if (data?.sample && typeof data.sample === "object") {
    fields = inferFieldsFromSample(data.sample);
    return withVirtualFields(template, fields);
  }
  return withVirtualFields(template, []);
}

export function ensureTemplateData(template, existingData = null) {
  if (!template || typeof template !== "object") {
    return template;
  }
  const current = normalizeDataMetadata(template.data);
  const fallback = normalizeDataMetadata(existingData);
  const data = current || fallback || {};

  if (!data.sample && fallback?.sample) {
    data.sample = structuredClone(fallback.sample);
  }
  if (!Array.isArray(data.fields) && Array.isArray(fallback?.fields)) {
    data.fields = structuredClone(fallback.fields);
  }
  if (!Array.isArray(data.fields) && data.sample && typeof data.sample === "object") {
    data.fields = inferFieldsFromSample(data.sample);
  }

  template.data = data;
  return template;
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

function withVirtualFields(template, fields) {
  const sampleData = template?.data?.sample || {};
  const generated = [
    { path: "page.number", label: "Page Number", type: "system", sample: "1" },
    { path: "page.index", label: "Page Index", type: "system", sample: "0" },
    { path: "page.total_pages", label: "Total Pages", type: "system", sample: "1" },
    { path: "page.count", label: "Page Count", type: "system", sample: "1" },
    { path: "date.today", label: "Today", type: "system", sample: formatDate(new Date()) },
    { path: "datetime.now", label: "Now", type: "system", sample: formatDateTime(new Date()) },
  ];
  if ((template?.bands || []).some((band) => ["group_header", "group_footer"].includes(band.type))) {
    generated.push(
      { path: "group.value", label: "Group Value", type: "group", sample: sampleGroupValue(template) },
      { path: "group.count", label: "Group Count", type: "group", sample: sampleGroupCount(template) }
    );
    for (const field of numericChildFields(template, fields)) {
      generated.push(
        { path: `group.sum.${field}`, label: `Group Sum ${field}`, type: "group", sample: "" },
        { path: `group.avg.${field}`, label: `Group Avg ${field}`, type: "group", sample: "" }
      );
    }
  }
  for (const arrayPath of arrayPaths(fields)) {
    generated.push({
      path: `report.count.${arrayPath}`,
      label: `Report Count ${arrayPath}`,
      type: "report",
      sample: String(getArrayByPath(sampleData, arrayPath).length)
    });
    for (const field of numericChildFields(template, fields, arrayPath)) {
      generated.push(
        { path: `report.sum.${arrayPath}.${field}`, label: `Report Sum ${field}`, type: "report", sample: "" },
        { path: `report.avg.${arrayPath}.${field}`, label: `Report Avg ${field}`, type: "report", sample: "" }
      );
    }
  }
  const byPath = new Map();
  for (const field of [...fields, ...generated]) {
    if (!byPath.has(field.path)) {
      byPath.set(field.path, field);
    }
  }
  return [...byPath.values()];
}

function arrayPaths(fields) {
  return [...new Set(
    fields
      .map((field) => String(field.path || ""))
      .filter((path) => path.endsWith("[]"))
      .map(normalizeArrayFieldPath)
      .filter(Boolean)
  )];
}

function numericChildFields(template, fields, forcedArrayPath = "") {
  const detail = (template?.bands || []).find((band) => band.id === "detail") || {};
  const groupBand = (template?.bands || []).find((band) => band.type === "group_header") || {};
  const arrayPath = forcedArrayPath || groupBand.group?.data_path || detail.repeat?.data_path || arrayPaths(fields)[0] || "";
  if (!arrayPath) {
    return [];
  }
  const sampleRows = getArrayByPath(template?.data?.sample || {}, arrayPath);
  const prefix = `${arrayPath}[].`;
  return fields
    .map((field) => normalizeFieldPath(field.path))
    .filter((path) => path.startsWith(prefix))
    .map((path) => path.slice(prefix.length))
    .filter((childPath) => sampleRows.some((row) => toNumber(getValueByPath(row, childPath)) !== null));
}

function sampleGroupValue(template) {
  const detail = (template?.bands || []).find((band) => band.id === "detail") || {};
  const groupBand = (template?.bands || []).find((band) => band.type === "group_header") || {};
  const arrayPath = groupBand.group?.data_path || detail.repeat?.data_path || "";
  const groupField = groupBand.group?.field || "";
  const row = getArrayByPath(template?.data?.sample || {}, arrayPath)[0] || {};
  return groupField ? String(getValueByPath(row, groupField) ?? "") : "";
}

function sampleGroupCount(template) {
  const detail = (template?.bands || []).find((band) => band.id === "detail") || {};
  const groupBand = (template?.bands || []).find((band) => band.type === "group_header") || {};
  const arrayPath = groupBand.group?.data_path || detail.repeat?.data_path || "";
  const groupField = groupBand.group?.field || "";
  const rows = getArrayByPath(template?.data?.sample || {}, arrayPath);
  if (!groupField || rows.length === 0) {
    return "";
  }
  const key = getValueByPath(rows[0] || {}, groupField);
  return String(rows.filter((row) => getValueByPath(row || {}, groupField) === key).length);
}

function aggregateCount(rows) {
  return Array.isArray(rows) ? rows.length : 0;
}

function aggregateRows(rows, operation, field) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => toNumber(getValueByPath(row || {}, field)))
    .filter((value) => value !== null);
  if (operation === "sum") {
    return formatNumber(values.reduce((sum, value) => sum + value, 0));
  }
  if (values.length === 0) {
    return "";
  }
  if (operation === "avg") {
    return formatNumber(values.reduce((sum, value) => sum + value, 0) / values.length);
  }
  if (operation === "min") {
    return formatNumber(Math.min(...values));
  }
  if (operation === "max") {
    return formatNumber(Math.max(...values));
  }
  return "";
}

function splitReportAggregatePath(sampleData, target) {
  const parts = String(target || "").split(".");
  for (let index = parts.length - 1; index > 0; index -= 1) {
    const arrayPath = parts.slice(0, index).join(".");
    if (getArrayByPath(sampleData, arrayPath).length > 0) {
      return { arrayPath, field: parts.slice(index).join(".") };
    }
  }
  if (parts.length >= 2) {
    return { arrayPath: parts.slice(0, -1).join("."), field: parts.at(-1) };
  }
  return { arrayPath: "", field: "" };
}

function toNumber(value) {
  if (typeof value === "boolean" || value === undefined || value === null) {
    return null;
  }
  const number = Number(String(value).replace(/,/g, "").trim());
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value) {
  return Number.isInteger(value) ? value : Number(value.toFixed(6));
}

function formatDate(value) {
  return `${value.getFullYear()}-${pad2(value.getMonth() + 1)}-${pad2(value.getDate())}`;
}

function formatDateTime(value) {
  return `${formatDate(value)} ${pad2(value.getHours())}:${pad2(value.getMinutes())}`;
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function walkValue(value, prefix, paths) {
  if (Array.isArray(value)) {
    if (!prefix) {
      value.slice(0, 1).forEach((item) => walkValue(item, "", paths));
      return;
    }
    paths.push(`${prefix}[]`);
    if (value.length === 0) {
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

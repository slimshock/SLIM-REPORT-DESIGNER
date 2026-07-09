const QR_GRID_SIZE = 29;
const QR_QUIET_ZONE = 4;
const QR_DATA_SIZE = 21;

export function appendQrSvg(container, {
  value = "QR Code",
  left = 0,
  top = 0,
  size = 0,
  foreground = "currentColor",
  background = "#ffffff"
} = {}) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("qrcode-grid");
  svg.setAttribute("viewBox", `0 0 ${QR_GRID_SIZE} ${QR_GRID_SIZE}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", String(value || "QR Code"));
  svg.setAttribute("shape-rendering", "crispEdges");
  svg.style.left = `${left}px`;
  svg.style.top = `${top}px`;
  svg.style.width = `${size}px`;
  svg.style.height = `${size}px`;

  if (!isTransparent(background)) {
    const backgroundRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    backgroundRect.setAttribute("width", String(QR_GRID_SIZE));
    backgroundRect.setAttribute("height", String(QR_GRID_SIZE));
    backgroundRect.setAttribute("fill", background);
    svg.appendChild(backgroundRect);
  }

  const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
  group.setAttribute("fill", foreground);
  for (const [rowIndex, row] of qrModuleMatrix(value).entries()) {
    for (const [colIndex, enabled] of row.entries()) {
      if (!enabled) {
        continue;
      }
      const cell = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      cell.setAttribute("x", String(colIndex));
      cell.setAttribute("y", String(rowIndex));
      cell.setAttribute("width", "1");
      cell.setAttribute("height", "1");
      group.appendChild(cell);
    }
  }
  svg.appendChild(group);
  container.appendChild(svg);
  return svg;
}

export function qrSvgMarkup(value = "QR Code", {
  foreground = "#111827",
  background = "#ffffff"
} = {}) {
  const safeValue = escapeHtml(value || "QR Code");
  const backgroundRect = isTransparent(background)
    ? ""
    : `<rect width="${QR_GRID_SIZE}" height="${QR_GRID_SIZE}" fill="${escapeHtml(background)}" />`;
  const cells = [];
  for (const [rowIndex, row] of qrModuleMatrix(value).entries()) {
    for (const [colIndex, enabled] of row.entries()) {
      if (enabled) {
        cells.push(`<rect x="${colIndex}" y="${rowIndex}" width="1" height="1" />`);
      }
    }
  }
  return `<svg role="img" aria-label="${safeValue}" viewBox="0 0 ${QR_GRID_SIZE} ${QR_GRID_SIZE}" xmlns="http://www.w3.org/2000/svg" shape-rendering="crispEdges" style="display:block;width:100%;height:100%">${backgroundRect}<g fill="${escapeHtml(foreground)}">${cells.join("")}</g></svg>`;
}

export function qrModuleMatrix(value = "QR Code") {
  const text = String(value || "QR Code");
  const seed = stableHash(text);
  const matrix = Array.from({ length: QR_GRID_SIZE }, () => Array(QR_GRID_SIZE).fill(false));
  const finderOrigins = [
    [QR_QUIET_ZONE, QR_QUIET_ZONE],
    [QR_QUIET_ZONE, QR_QUIET_ZONE + QR_DATA_SIZE - 7],
    [QR_QUIET_ZONE + QR_DATA_SIZE - 7, QR_QUIET_ZONE]
  ];

  for (const [row, col] of finderOrigins) {
    drawFinder(matrix, row, col);
  }

  const timingRow = QR_QUIET_ZONE + 6;
  const timingCol = QR_QUIET_ZONE + 6;
  for (let index = 8; index < QR_DATA_SIZE - 8; index += 1) {
    const enabled = index % 2 === 0;
    matrix[timingRow][QR_QUIET_ZONE + index] = enabled;
    matrix[QR_QUIET_ZONE + index][timingCol] = enabled;
  }

  for (let innerRow = 0; innerRow < QR_DATA_SIZE; innerRow += 1) {
    for (let innerCol = 0; innerCol < QR_DATA_SIZE; innerCol += 1) {
      if (reserved(innerRow, innerCol)) {
        continue;
      }
      const row = QR_QUIET_ZONE + innerRow;
      const col = QR_QUIET_ZONE + innerCol;
      const charCode = text.charCodeAt((innerRow * QR_DATA_SIZE + innerCol) % text.length);
      const mixed = (
        seed
        ^ Math.imul(innerRow + 1, 0x45d9f3b)
        ^ Math.imul(innerCol + 1, 0x27d4eb2d)
        ^ Math.imul(charCode, innerRow + innerCol + 1)
      ) >>> 0;
      matrix[row][col] = [0, 2, 5].includes(mixed % 7);
    }
  }

  return matrix;
}

function drawFinder(matrix, top, left) {
  for (let row = 0; row < 7; row += 1) {
    for (let col = 0; col < 7; col += 1) {
      const edge = row === 0 || row === 6 || col === 0 || col === 6;
      const core = row >= 2 && row <= 4 && col >= 2 && col <= 4;
      matrix[top + row][left + col] = edge || core;
    }
  }
}

function reserved(row, col) {
  const finderOrigins = [
    [0, 0],
    [0, QR_DATA_SIZE - 7],
    [QR_DATA_SIZE - 7, 0]
  ];
  return finderOrigins.some(([finderRow, finderCol]) => (
    row >= finderRow - 1
    && row <= finderRow + 7
    && col >= finderCol - 1
    && col <= finderCol + 7
  )) || row === 6 || col === 6;
}

function stableHash(value) {
  let seed = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    seed ^= value.charCodeAt(index);
    seed = Math.imul(seed, 16777619) >>> 0;
  }
  return seed;
}

function isTransparent(value) {
  return ["", "none", "transparent"].includes(String(value || "").trim().toLowerCase());
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  })[char]);
}

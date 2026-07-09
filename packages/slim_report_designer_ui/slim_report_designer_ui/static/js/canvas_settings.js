const STORAGE_KEY = "slim_report_designer.canvas_settings";
const ZOOM_STEPS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2];

export function defaultCanvasSettings() {
  return {
    zoom: 1,
    grid_size: 10,
    show_grid: true,
    snap_to_grid: true,
    show_sample_data: false,
    show_repeated_rows: false
  };
}

export function loadCanvasSettings() {
  try {
    return normalizeCanvasSettings(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
  } catch (error) {
    return defaultCanvasSettings();
  }
}

export function saveCanvasSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeCanvasSettings(settings)));
}

export function normalizeCanvasSettings(settings) {
  const defaults = defaultCanvasSettings();
  return {
    zoom: clampZoom(Number(settings?.zoom) || defaults.zoom),
    grid_size: clampGridSize(Number(settings?.grid_size) || defaults.grid_size),
    show_grid: settings?.show_grid === undefined ? defaults.show_grid : Boolean(settings.show_grid),
    snap_to_grid: settings?.snap_to_grid === undefined
      ? defaults.snap_to_grid
      : Boolean(settings.snap_to_grid),
    show_sample_data: settings?.show_sample_data === undefined
      ? defaults.show_sample_data
      : Boolean(settings.show_sample_data),
    show_repeated_rows: settings?.show_repeated_rows === undefined
      ? defaults.show_repeated_rows
      : Boolean(settings.show_repeated_rows)
  };
}

export function zoomIn(currentZoom) {
  return nextZoomStep(currentZoom, 1);
}

export function zoomOut(currentZoom) {
  return nextZoomStep(currentZoom, -1);
}

export function zoomPercent(zoom) {
  return `${Math.round(clampZoom(zoom) * 100)}%`;
}

export function screenDeltaToRealDelta(delta, zoom) {
  return delta / clampZoom(zoom);
}

export function snapValue(value, gridSize) {
  const grid = Number(gridSize) || 1;
  if (grid <= 0) {
    return value;
  }
  return Math.round(value / grid) * grid;
}

export function maybeSnap(value, settings, unitScale = 1) {
  if (!settings?.snap_to_grid) {
    return value;
  }
  return snapValue(value, gridSizeForUnit(settings, unitScale));
}

export function gridSizeForUnit(settings, unitScale = 1) {
  const scale = Number(unitScale) || 1;
  return clampGridSize(settings?.grid_size) / scale;
}

export function clampGridSize(value) {
  const number = Math.round(Number(value) || 10);
  return Math.min(Math.max(number, 1), 100);
}

export function clampZoom(value) {
  const number = Number(value) || 1;
  return Math.min(Math.max(number, ZOOM_STEPS[0]), ZOOM_STEPS[ZOOM_STEPS.length - 1]);
}

function nextZoomStep(currentZoom, direction) {
  const zoom = clampZoom(currentZoom);
  if (direction > 0) {
    return ZOOM_STEPS.find((step) => step > zoom) || ZOOM_STEPS[ZOOM_STEPS.length - 1];
  }
  return [...ZOOM_STEPS].reverse().find((step) => step < zoom) || ZOOM_STEPS[0];
}

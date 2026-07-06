const ICONS = {
  save: '<path d="M5 3h10l4 4v14H5z"/><path d="M8 3v6h8V3"/><path d="M8 17h8"/>',
  preview: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
  pdf: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M8 16h8"/><path d="M8 19h5"/>',
  download: '<path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 20h14"/>',
  upload: '<path d="M12 21V9"/><path d="M8 13l4-4 4 4"/><path d="M5 4h14"/>',
  copy: '<path d="M8 8h11v13H8z"/><path d="M5 16H3V3h13v2"/>',
  duplicate: '<path d="M8 8h11v11H8z"/><path d="M5 16H3V3h11v2"/><path d="M13 11v5"/><path d="M10.5 13.5h5"/>',
  delete: '<path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 14h10l1-14"/><path d="M9 7V4h6v3"/>',
  undo: '<path d="M9 7H4v5"/><path d="M4 12l5-5"/><path d="M5 12h8a5 5 0 1 1 0 10h-2"/>',
  redo: '<path d="M15 7h5v5"/><path d="M20 12l-5-5"/><path d="M19 12h-8a5 5 0 1 0 0 10h2"/>',
  text: '<path d="M5 5h14"/><path d="M12 5v14"/><path d="M9 19h6"/>',
  field: '<path d="M8 7H5v10h3"/><path d="M16 7h3v10h-3"/><path d="M10 15l4-6"/>',
  database: '<ellipse cx="12" cy="5" rx="7" ry="3"/><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5"/><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  line: '<path d="M4 12h16"/>',
  rectangle: '<rect x="4" y="6" width="16" height="12"/>',
  image: '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M4 16l4-4 3 3 2-2 7 6"/>',
  table: '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 10h16"/><path d="M4 14h16"/><path d="M9 5v14"/><path d="M15 5v14"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/><path d="M12 7v5l4 2"/>',
  restore: '<path d="M4 12a8 8 0 1 0 3-6.3"/><path d="M4 5v5h5"/><path d="M12 8v5h4"/>',
  close: '<path d="M6 6l12 12"/><path d="M18 6L6 18"/>',
  "zoom-in": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/><path d="M11 8v6"/><path d="M8 11h6"/>',
  "zoom-out": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/><path d="M8 11h6"/>',
  "zoom-reset": '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  "fit-page": '<path d="M5 9V5h4"/><path d="M19 9V5h-4"/><path d="M5 15v4h4"/><path d="M19 15v4h-4"/><rect x="8" y="7" width="8" height="10"/>',
  "align-left": '<path d="M5 6h14"/><path d="M5 10h9"/><path d="M5 14h14"/><path d="M5 18h9"/>',
  "align-center": '<path d="M5 6h14"/><path d="M8 10h8"/><path d="M5 14h14"/><path d="M8 18h8"/>',
  "align-right": '<path d="M5 6h14"/><path d="M10 10h9"/><path d="M5 14h14"/><path d="M10 18h9"/>',
  "align-top": '<path d="M5 5h14"/><path d="M8 9h8"/><path d="M10 13h4"/><path d="M10 17h4"/>',
  "align-middle": '<path d="M5 12h14"/><path d="M8 7h8"/><path d="M8 17h8"/>',
  "align-bottom": '<path d="M5 19h14"/><path d="M8 15h8"/><path d="M10 11h4"/><path d="M10 7h4"/>'
  ,
  "distribute-horizontal": '<path d="M4 5v14"/><path d="M20 5v14"/><rect x="7" y="8" width="3" height="8"/><rect x="14" y="8" width="3" height="8"/>',
  "distribute-vertical": '<path d="M5 4h14"/><path d="M5 20h14"/><rect x="8" y="7" width="8" height="3"/><rect x="8" y="14" width="8" height="3"/>',
  "bring-forward": '<rect x="8" y="4" width="10" height="10"/><rect x="4" y="10" width="10" height="10"/>',
  "send-backward": '<rect x="4" y="10" width="10" height="10"/><rect x="8" y="4" width="10" height="10"/>',
  "bring-front": '<rect x="7" y="3" width="12" height="12"/><path d="M5 9v10h10"/>',
  "send-back": '<rect x="5" y="9" width="12" height="12"/><path d="M9 5h10v10"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  unlock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M16 10V7a4 4 0 0 0-7.5-2"/>'
};

export function icon(name) {
  const body = ICONS[name] || "";
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

export function applyIcon(element, name) {
  element.innerHTML = icon(name);
}

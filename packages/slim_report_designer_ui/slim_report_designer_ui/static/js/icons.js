const ICONS = {
  save: '<path d="M5 3h10l4 4v14H5z"/><path d="M8 3v6h8V3"/><path d="M8 17h8"/>',
  preview: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
  pdf: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M8 16h8"/><path d="M8 19h5"/>',
  download: '<path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M5 20h14"/>',
  upload: '<path d="M12 21V9"/><path d="M8 13l4-4 4 4"/><path d="M5 4h14"/>',
  copy: '<path d="M8 8h11v13H8z"/><path d="M5 16H3V3h13v2"/>',
  duplicate: '<path d="M8 8h11v11H8z"/><path d="M5 16H3V3h11v2"/><path d="M13 11v5"/><path d="M10.5 13.5h5"/>',
  delete: '<path d="M4 7h16"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M6 7l1 14h10l1-14"/><path d="M9 7V4h6v3"/>',
  text: '<path d="M5 5h14"/><path d="M12 5v14"/><path d="M9 19h6"/>',
  field: '<path d="M8 7H5v10h3"/><path d="M16 7h3v10h-3"/><path d="M10 15l4-6"/>',
  line: '<path d="M4 12h16"/>',
  rectangle: '<rect x="4" y="6" width="16" height="12"/>',
  image: '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="M4 16l4-4 3 3 2-2 7 6"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6"/><path d="M12 7v5l4 2"/>',
  restore: '<path d="M4 12a8 8 0 1 0 3-6.3"/><path d="M4 5v5h5"/><path d="M12 8v5h4"/>',
  close: '<path d="M6 6l12 12"/><path d="M18 6L6 18"/>',
  "align-left": '<path d="M5 6h14"/><path d="M5 10h9"/><path d="M5 14h14"/><path d="M5 18h9"/>',
  "align-center": '<path d="M5 6h14"/><path d="M8 10h8"/><path d="M5 14h14"/><path d="M8 18h8"/>',
  "align-right": '<path d="M5 6h14"/><path d="M10 10h9"/><path d="M5 14h14"/><path d="M10 18h9"/>',
  "align-top": '<path d="M5 5h14"/><path d="M8 9h8"/><path d="M10 13h4"/><path d="M10 17h4"/>',
  "align-middle": '<path d="M5 12h14"/><path d="M8 7h8"/><path d="M8 17h8"/>',
  "align-bottom": '<path d="M5 19h14"/><path d="M8 15h8"/><path d="M10 11h4"/><path d="M10 7h4"/>'
};

export function icon(name) {
  const body = ICONS[name] || "";
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

export function applyIcon(element, name) {
  element.innerHTML = icon(name);
}

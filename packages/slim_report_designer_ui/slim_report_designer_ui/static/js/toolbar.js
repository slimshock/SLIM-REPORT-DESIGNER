import { icon } from "./icons.js";
import { zoomPercent } from "./canvas_settings.js";

export function createToolbar({ container, onCommand }) {
  const groups = [
    {
      label: "File",
      actions: [
        ["newReport", "New Report", "text-action", "Create a new report", "New Report", "plus"],
        ["save", "Save", "primary text-action", "Save template", "Save", "save"]
      ]
    },
    {
      label: "Data",
      actions: [
        ["dataSources", "Data Sources", "text-action", "Manage MySQL data sources", "Data Sources", "database"],
        ["datasets", "Datasets", "text-action", "Manage report datasets", "Datasets", "table"]
      ]
    },
    {
      label: "Preview",
      actions: [
        ["preview", "Preview", "text-action", "Preview report", "Preview", "preview"],
        ["printPreview", "Print Preview", "text-action", "Open printable report preview", "Print", "preview"],
        ["exportPdf", "Export PDF", "icon-action", "Export report as PDF", "", "pdf"]
      ]
    },
    {
      label: "JSON",
      actions: [
        ["exportJson", "Export JSON", "icon-action", "Download template JSON", "", "download"],
        ["importJson", "Import JSON", "icon-action", "Import template JSON", "", "upload"],
        ["copyJson", "Copy JSON", "icon-action", "Copy template JSON to clipboard", "", "copy"]
      ]
    },
    {
      label: "Object",
      actions: [
        ["undo", "Undo", "icon-action", "Undo last change", "", "undo"],
        ["redo", "Redo", "icon-action", "Redo last undone change", "", "redo"],
        ["duplicate", "Duplicate", "icon-action", "Duplicate selected object", "", "duplicate"],
        ["delete", "Delete", "danger icon-action", "Delete selected object", "", "delete"]
      ]
    },
    {
      label: "Align",
      actions: [
        ["alignLeft", "Align Left", "icon-action", "Align selected left", "", "align-left"],
        ["alignCenter", "Align Center", "icon-action", "Align selected center", "", "align-center"],
        ["alignRight", "Align Right", "icon-action", "Align selected right", "", "align-right"],
        ["alignTop", "Align Top", "icon-action", "Align selected top", "", "align-top"],
        ["alignMiddle", "Align Middle", "icon-action", "Align selected middle", "", "align-middle"],
        ["alignBottom", "Align Bottom", "icon-action", "Align selected bottom", "", "align-bottom"],
        ["distributeHorizontal", "Distribute Horizontal", "icon-action", "Distribute selected horizontally", "", "distribute-horizontal"],
        ["distributeVertical", "Distribute Vertical", "icon-action", "Distribute selected vertically", "", "distribute-vertical"]
      ]
    },
    {
      label: "Layer",
      actions: [
        ["bringForward", "Bring Forward", "icon-action", "Bring selected forward", "", "bring-forward"],
        ["sendBackward", "Send Backward", "icon-action", "Send selected backward", "", "send-backward"],
        ["bringToFront", "Bring To Front", "icon-action", "Bring selected to front", "", "bring-front"],
        ["sendToBack", "Send To Back", "icon-action", "Send selected to back", "", "send-back"],
        ["lockSelected", "Lock Selected", "icon-action", "Lock selected objects", "", "lock"],
        ["unlockSelected", "Unlock Selected", "icon-action", "Unlock selected objects", "", "unlock"]
      ]
    },
    {
      label: "History",
      actions: [
        ["history", "Version History", "icon-action", "View Version History", "", "history"]
      ]
    },
    {
      label: "Bands",
      actions: [
        ["addGroup", "Add Group", "text-action", "Add group header and footer bands", "Group", "duplicate"]
      ]
    }
  ];

  container.innerHTML = "";
  for (const group of groups) {
    const groupElement = document.createElement("div");
    groupElement.className = "toolbar-group";
    groupElement.setAttribute("aria-label", `${group.label} actions`);

    for (const [command, text, variant, title, display, iconName] of group.actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `toolbar-button ${variant}`.trim();
      button.dataset.command = command;
      button.title = title;
      button.setAttribute("aria-label", text);
      button.innerHTML = `${icon(iconName)}${display ? `<span>${display}</span>` : ""}<span class="sr-only">${text}</span>`;
      groupElement.appendChild(button);
    }

    container.appendChild(groupElement);
  }
  container.appendChild(canvasControls());

  container.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-command]");
    if (button && !button.disabled) {
      onCommand(button.dataset.command);
    }
  });
  container.addEventListener("change", (event) => {
    const bandInput = event.target.closest("[data-active-band]");
    if (bandInput) {
      onCommand("activeBand", { bandId: bandInput.value });
      return;
    }
    const input = event.target.closest("[data-canvas-setting]");
    if (!input) {
      return;
    }
    const value = input.type === "checkbox" ? input.checked : input.value;
    onCommand("canvasSetting", {
      key: input.dataset.canvasSetting,
      value
    });
  });

  return {
    render({
      hasSelection,
      selectionCount = hasSelection ? 1 : 0,
      canvasSettings,
      canUndo = false,
      canRedo = false,
      activeBandId = "detail",
      bands = []
    }) {
      for (const command of ["duplicate", "delete"]) {
        const button = container.querySelector(`[data-command="${command}"]`);
        if (button) {
          button.disabled = !hasSelection;
        }
      }
      for (const [command, enabled] of [["undo", canUndo], ["redo", canRedo]]) {
        const button = container.querySelector(`[data-command="${command}"]`);
        if (button) {
          button.disabled = !enabled;
        }
      }
      setCommandGroupDisabled(container, [
        "alignLeft",
        "alignCenter",
        "alignRight",
        "alignTop",
        "alignMiddle",
        "alignBottom"
      ], selectionCount < 2);
      setCommandGroupDisabled(container, [
        "distributeHorizontal",
        "distributeVertical"
      ], selectionCount < 3);
      setCommandGroupDisabled(container, [
        "bringForward",
        "sendBackward",
        "bringToFront",
        "sendToBack",
        "lockSelected",
        "unlockSelected"
      ], selectionCount < 1);
      const zoomDisplay = container.querySelector("[data-zoom-display]");
      if (zoomDisplay) {
        zoomDisplay.textContent = zoomPercent(canvasSettings?.zoom || 1);
      }
      const gridInput = container.querySelector('[data-canvas-setting="grid_size"]');
      if (gridInput) {
        gridInput.value = String(canvasSettings?.grid_size || 10);
      }
      for (const key of ["show_grid", "snap_to_grid", "show_sample_data", "show_repeated_rows"]) {
        const checkbox = container.querySelector(`[data-canvas-setting="${key}"]`);
        if (checkbox) {
          checkbox.checked = Boolean(canvasSettings?.[key]);
        }
      }
      const bandSelect = container.querySelector("[data-active-band]");
      if (bandSelect) {
        const current = bandSelect.value;
        bandSelect.innerHTML = "";
        for (const band of bands) {
          const option = document.createElement("option");
          option.value = band.id;
          option.textContent = band.name || band.id;
          bandSelect.appendChild(option);
        }
        bandSelect.value = activeBandId || current || "detail";
      }
    }
  };
}

function setCommandGroupDisabled(container, commands, disabled) {
  for (const command of commands) {
    const button = container.querySelector(`[data-command="${command}"]`);
    if (button) {
      button.disabled = disabled;
    }
  }
}

function canvasControls() {
  const group = document.createElement("div");
  group.className = "toolbar-group canvas-controls";
  group.setAttribute("aria-label", "Canvas controls");
  group.append(
    bandSelector(),
    commandButton("zoomOut", "Zoom out", "zoom-out"),
    zoomDisplay(),
    commandButton("zoomIn", "Zoom in", "zoom-in"),
    commandButton("resetZoom", "Reset zoom to 100%", "zoom-reset"),
    commandButton("fitPage", "Fit page", "fit-page"),
    gridSizeControl(),
    checkboxControl("show_grid", "Show grid", "Grid"),
    checkboxControl("snap_to_grid", "Snap to grid", "Snap"),
    checkboxControl("show_sample_data", "Show sample data", "Sample"),
    checkboxControl("show_repeated_rows", "Show repeated sample rows", "Rows")
  );
  return group;
}

function bandSelector() {
  const label = document.createElement("label");
  label.className = "toolbar-field";
  label.title = "Active band";
  label.append(document.createTextNode("Band"));
  const select = document.createElement("select");
  select.dataset.activeBand = "true";
  select.setAttribute("aria-label", "Active band");
  label.appendChild(select);
  return label;
}

function commandButton(command, label, iconName) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "toolbar-button icon-action";
  button.dataset.command = command;
  button.title = label;
  button.setAttribute("aria-label", label);
  button.innerHTML = `${icon(iconName)}<span class="sr-only">${label}</span>`;
  return button;
}

function zoomDisplay() {
  const output = document.createElement("span");
  output.className = "zoom-display";
  output.dataset.zoomDisplay = "true";
  output.textContent = "100%";
  return output;
}

function gridSizeControl() {
  const label = document.createElement("label");
  label.className = "toolbar-field";
  label.title = "Grid size";
  label.append(document.createTextNode("Grid"));
  const select = document.createElement("select");
  select.dataset.canvasSetting = "grid_size";
  select.setAttribute("aria-label", "Grid size");
  for (const value of [5, 10, 20, 25, 50]) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(value);
    select.appendChild(option);
  }
  label.appendChild(select);
  return label;
}

function checkboxControl(key, label, text) {
  const wrapper = document.createElement("label");
  wrapper.className = "toolbar-toggle";
  wrapper.title = label;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.dataset.canvasSetting = key;
  input.setAttribute("aria-label", label);
  wrapper.append(input, document.createTextNode(text));
  return wrapper;
}

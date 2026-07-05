import { icon } from "./icons.js";

export function createToolbar({ container, onCommand }) {
  const groups = [
    {
      label: "File",
      actions: [
        ["save", "Save", "primary text-action", "Save template", "Save", "save"]
      ]
    },
    {
      label: "Preview",
      actions: [
        ["preview", "Preview", "text-action", "Preview report", "Preview", "preview"],
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
        ["duplicate", "Duplicate", "icon-action", "Duplicate selected object", "", "duplicate"],
        ["delete", "Delete", "danger icon-action", "Delete selected object", "", "delete"]
      ]
    },
    {
      label: "History",
      actions: [
        ["history", "Version History", "icon-action", "View Version History", "", "history"]
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

  container.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-command]");
    if (button && !button.disabled) {
      onCommand(button.dataset.command);
    }
  });

  return {
    render({ hasSelection }) {
      for (const command of ["duplicate", "delete"]) {
        const button = container.querySelector(`[data-command="${command}"]`);
        if (button) {
          button.disabled = !hasSelection;
        }
      }
    }
  };
}

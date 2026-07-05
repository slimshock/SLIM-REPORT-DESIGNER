export function createToolbar({ container, onCommand }) {
  const groups = [
    {
      label: "File",
      actions: [
        ["save", "Save", "primary text-action", "Save template", "Save"]
      ]
    },
    {
      label: "Preview",
      actions: [
        ["preview", "Preview", "text-action", "Preview report", "Preview"],
        ["exportPdf", "Export PDF", "icon-action", "Export report as PDF", "PDF"]
      ]
    },
    {
      label: "JSON",
      actions: [
        ["exportJson", "Export JSON", "icon-action", "Download template JSON", "DL"],
        ["importJson", "Import JSON", "icon-action", "Import template JSON", "UP"],
        ["copyJson", "Copy JSON", "icon-action", "Copy template JSON to clipboard", "CP"]
      ]
    },
    {
      label: "Object",
      actions: [
        ["duplicate", "Duplicate", "icon-action", "Duplicate selected object", "DU"],
        ["delete", "Delete", "danger icon-action", "Delete selected object", "DEL"]
      ]
    }
  ];

  container.innerHTML = "";
  for (const group of groups) {
    const groupElement = document.createElement("div");
    groupElement.className = "toolbar-group";
    groupElement.setAttribute("aria-label", `${group.label} actions`);

    for (const [command, text, variant, title, display] of group.actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `toolbar-button ${variant}`.trim();
      button.dataset.command = command;
      button.textContent = display;
      button.title = title;
      button.setAttribute("aria-label", text);
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

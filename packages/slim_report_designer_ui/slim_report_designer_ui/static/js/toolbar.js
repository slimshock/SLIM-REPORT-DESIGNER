export function createToolbar({ container, onCommand }) {
  const actions = [
    ["save", "Save", "primary"],
    ["preview", "Preview", ""],
    ["exportPdf", "Export PDF", ""],
    ["exportJson", "Export JSON", ""],
    ["importJson", "Import JSON", ""],
    ["copyJson", "Copy JSON", ""],
    ["duplicate", "Duplicate", ""],
    ["delete", "Delete", "danger"]
  ];

  container.innerHTML = "";
  for (const [command, label, variant] of actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `toolbar-button ${variant}`.trim();
    button.dataset.command = command;
    button.textContent = label;
    container.appendChild(button);
  }

  container.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-command]");
    if (button) {
      onCommand(button.dataset.command);
    }
  });
}

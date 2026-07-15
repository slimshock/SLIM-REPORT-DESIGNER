import { cancelLivePreview, startLivePreview } from "./api.js";
import { applyIcon } from "./icons.js";

export function createLivePreview({ root, getTemplate, onStatus }) {
  const ui = {
    close: root.querySelector("#live-preview-close"),
    status: root.querySelector("#live-preview-status"),
    summary: root.querySelector("#live-preview-summary"),
    frame: root.querySelector("#live-preview-frame"),
    cancel: root.querySelector("#live-preview-cancel")
  };
  let activeRequestId = "";
  let active = false;
  let cancelRequested = false;
  let opener = null;

  applyIcon(ui.close, "close");
  ui.close.addEventListener("click", close);
  ui.cancel.addEventListener("click", cancel);
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !active) {
      event.preventDefault();
      close();
    }
  });

  return { open, close, cancel, isActive: () => active };

  async function open(datasetId, parameterValues = {}, options = {}) {
    if (active) {
      return;
    }
    opener = options.openingControl || document.activeElement;
    if (opener && "disabled" in opener) {
      opener.disabled = true;
    }
    root.hidden = false;
    clearOutput();
    active = true;
    cancelRequested = false;
    activeRequestId = createRequestId();
    ui.close.disabled = true;
    ui.cancel.disabled = false;
    setStatus("Preparing report preview...", "loading");
    onStatus("Preparing report preview...");
    await nextFrame();
    setStatus("Executing dataset...", "loading");
    try {
      const result = await startLivePreview(getTemplate(), {
        requestId: activeRequestId,
        datasetId,
        parameterValues,
        options: { maxRows: options.maxRows || 500 }
      });
      if (cancelRequested) {
        setStatus("Report preview was cancelled.", "cancelled");
        onStatus("Report preview was cancelled.");
        return;
      }
      setStatus("Rendering report...", "loading");
      await nextFrame();
      ui.frame.srcdoc = result.html || "";
      renderSummary(result.summary || {});
      const empty = Number(result.summary?.rowCount || 0) === 0;
      setStatus(
        empty ? "No rows matched the selected parameters." : "Report preview ready.",
        empty ? "empty" : "success"
      );
      onStatus(empty ? "Live preview returned no rows." : "Live preview opened.");
    } catch (error) {
      const cancelled = cancelRequested || error.code === "preview_cancelled";
      setStatus(
        cancelled ? "Report preview was cancelled." : error.message,
        cancelled ? "cancelled" : "error"
      );
      onStatus(cancelled ? "Report preview was cancelled." : error.message);
    } finally {
      active = false;
      activeRequestId = "";
      ui.cancel.disabled = true;
      ui.close.disabled = false;
      if (opener && "disabled" in opener) {
        opener.disabled = false;
      }
      ui.close.focus();
    }
  }

  async function cancel() {
    if (!active || cancelRequested) {
      return;
    }
    cancelRequested = true;
    ui.cancel.disabled = true;
    setStatus("Cancelling preview...", "loading");
    onStatus("Cancelling preview...");
    await cancelLivePreview(activeRequestId);
  }

  function close() {
    if (active) {
      cancel();
      return;
    }
    root.hidden = true;
    clearOutput();
    setStatus("", "");
    opener?.focus?.();
    opener = null;
  }

  function clearOutput() {
    ui.frame.srcdoc = "";
    ui.frame.removeAttribute("src");
    ui.summary.replaceChildren();
  }

  function renderSummary(summary) {
    const values = [
      `${Number(summary.rowCount || 0)} rows`,
      `${Number(summary.pageCount || 0)} pages`,
      `${Math.round(Number(summary.elapsedMs || 0))} ms`
    ];
    for (const value of values) {
      const item = document.createElement("span");
      item.textContent = value;
      ui.summary.appendChild(item);
    }
    for (const warning of summary.warnings || []) {
      const item = document.createElement("span");
      item.className = "is-warning";
      item.textContent = warning.message;
      ui.summary.appendChild(item);
    }
  }

  function setStatus(message, kind) {
    ui.status.textContent = message;
    ui.status.className = `live-preview-status${kind ? ` is-${kind}` : ""}`;
  }
}

function createRequestId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(24);
  window.crypto.getRandomValues(bytes);
  return [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
}

function nextFrame() {
  return new Promise((resolve) => window.requestAnimationFrame(resolve));
}

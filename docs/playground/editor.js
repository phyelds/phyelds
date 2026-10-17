/*
 * The editor of the playground: a textarea over the same code, highlighted. The
 * layers share font, size and padding, so the text lines up to the pixel, and the
 * textarea keeps the caret, the selection and undo. The highlighted layer is made
 * of divs, not pre and code, so that nothing takes it for a code block.
 */
const INDENT = "    ";

/** Binds the editor to `textarea`; `onRun` runs on Ctrl+Enter (Cmd+Enter on a Mac). */
export function createEditor(textarea, { onRun }) {
  const layer = document.createElement("div");
  layer.className = "pg-highlight";
  layer.setAttribute("aria-hidden", "true");
  const highlighted = document.createElement("div");
  highlighted.className = "pg-layer-text";
  layer.append(highlighted);
  textarea.before(layer);

  function sync() {
    // Moved rather than scrolled: the textarea can scroll further, past its scrollbars.
    highlighted.style.transform = `translate(${-textarea.scrollLeft}px, ${-textarea.scrollTop}px)`;
  }

  function refresh() {
    // A trailing newline would be invisible in the layer: a space keeps the last line.
    highlighted.innerHTML = `${globalThis.highlightPython(textarea.value)} `;
    sync();
  }

  textarea.addEventListener("input", refresh);
  textarea.addEventListener("scroll", sync);
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      onRun();
    } else if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      textarea.setRangeText(INDENT, textarea.selectionStart, textarea.selectionEnd, "end");
      textarea.dispatchEvent(new Event("input"));
    }
  });

  return {
    get code() {
      return textarea.value;
    },
    setCode(code) {
      textarea.value = code;
      textarea.scrollTop = 0;
      textarea.scrollLeft = 0;
      refresh();
    },
  };
}

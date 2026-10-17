/*
 * The editor of the playground: a textarea over the same code, highlighted, and
 * under both the marks of the watched expressions. The layers share font, size
 * and padding, so the text lines up to the pixel, and the textarea keeps the caret,
 * the selection and undo. The other layers are made of divs, not pre and code, so
 * that nothing takes them for code blocks.
 */
const INDENT = "    ";

const escape = (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

/** What an edit changed from `before` to `after`: `before` from `start` to `end`, with a change of length `delta`. */
function difference(before, after) {
  const shortest = Math.min(before.length, after.length);
  let start = 0;
  while (start < shortest && before[start] === after[start]) start += 1;
  let kept = 0;
  while (kept < shortest - start && before[before.length - 1 - kept] === after[after.length - 1 - kept]) kept += 1;
  return { start, end: before.length - kept, delta: after.length - before.length };
}

/** Where a range of the code is after `change`: shifted if the edit came before it, gone if it went through it. */
export function shifted(range, change) {
  if (range.end <= change.start) return range;
  if (range.start >= change.end) return { ...range, start: range.start + change.delta, end: range.end + change.delta };
  return null;
}

/**
 * Binds the editor to `textarea`. `onRun` runs on Ctrl+Enter and `onWatch` on
 * Ctrl+Shift+Enter (Cmd on a Mac); `onEdit` receives every change of the code.
 */
export function createEditor(textarea, { onRun, onWatch, onEdit }) {
  const layer = (className) => {
    const outer = document.createElement("div");
    outer.className = className;
    outer.setAttribute("aria-hidden", "true");
    const inner = document.createElement("div");
    inner.className = "pg-layer-text";
    outer.append(inner);
    textarea.before(outer);
    return inner;
  };
  const marked = layer("pg-marks");
  const highlighted = layer("pg-highlight");
  let marks = [];
  let last = textarea.value;

  function sync() {
    // Moved rather than scrolled: the textarea can scroll further, past its scrollbars.
    const shift = `translate(${-textarea.scrollLeft}px, ${-textarea.scrollTop}px)`;
    highlighted.style.transform = shift;
    marked.style.transform = shift;
  }

  /** The marks, as transparent text cut at every edge of a mark, so that nested marks need no nested tags. */
  function renderMarks() {
    const code = textarea.value;
    const edges = [...new Set([0, code.length, ...marks.flatMap(({ start, end }) => [start, end])])].sort((a, b) => a - b);
    let html = "";
    for (let k = 0; k + 1 < edges.length; k += 1) {
      const [from, to] = [edges[k], edges[k + 1]];
      const covering = marks.filter(({ start, end }) => start <= from && to <= end);
      const piece = escape(code.slice(from, to));
      const focused = covering.some((mark) => mark.focused) ? " is-focused" : "";
      html += covering.length ? `<span class="pg-mark${focused}" data-depth="${Math.min(covering.length, 3)}">${piece}</span>` : piece;
    }
    marked.innerHTML = `${html} `;
  }

  function refresh() {
    // A trailing newline would be invisible in the layer: a space keeps the last line.
    highlighted.innerHTML = `${globalThis.highlightPython(textarea.value)} `;
    renderMarks();
    sync();
  }

  textarea.addEventListener("input", () => {
    const change = difference(last, textarea.value);
    last = textarea.value;
    onEdit(change);
    refresh();
  });
  textarea.addEventListener("scroll", sync);
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      if (event.shiftKey) onWatch();
      else onRun();
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
      last = code;
      marks = [];
      textarea.scrollTop = 0;
      textarea.scrollLeft = 0;
      refresh();
    },
    /** The selection, as offsets in the code; the same twice for the caret. */
    selection: () => [textarea.selectionStart, textarea.selectionEnd],
    select(start, end) {
      textarea.focus();
      textarea.setSelectionRange(start, end);
    },
    /** Marks ranges of the code, each {start, end, focused}. */
    setMarks(ranges) {
      marks = ranges;
      renderMarks();
    },
  };
}

/*
 * The editor of the playground: a textarea over the same code, highlighted, and
 * under both the marks of the watched expressions. The layers share font, size
 * and padding, so the text lines up to the pixel, and the textarea keeps the caret,
 * the selection and undo. The other layers are made of divs, not pre and code, so
 * that nothing takes them for code blocks. A list under the caret offers the names
 * that complete the code.
 */
const INDENT = "    ";
const WAIT_MS = 150; // typing pauses this long before the editor asks for completions
const WORD = /[A-Za-z_]\w*$/;

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
 * Ctrl+Shift+Enter (Cmd on a Mac); `onEdit` receives every change of the code;
 * `onComplete(code, offset)` resolves to the names that complete it at the caret.
 */
export function createEditor(textarea, { onRun, onWatch, onEdit, onComplete }) {
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

  const completion = createCompletion(textarea, onComplete);

  textarea.addEventListener("input", () => {
    const change = difference(last, textarea.value);
    last = textarea.value;
    onEdit(change);
    refresh();
    completion.typed();
  });
  textarea.addEventListener("scroll", () => {
    sync();
    completion.hide();
  });
  textarea.addEventListener("blur", () => completion.hide());
  textarea.addEventListener("keydown", (event) => {
    if (completion.key(event)) {
      event.preventDefault();
    } else if (event.key === " " && event.ctrlKey) {
      event.preventDefault();
      completion.ask();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
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
      completion.hide();
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

/**
 * The list of the names that complete the code at the caret of `textarea`, which
 * `onComplete(code, offset)` finds. It opens as a name or a dot is typed, or on demand.
 */
function createCompletion(textarea, onComplete) {
  const list = document.createElement("ul");
  list.className = "pg-complete";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "Completions");
  list.hidden = true;
  textarea.parentElement.append(list);
  let names = [];
  let chosen = 0;
  let asked = 0; // the last question: the answers to older ones come too late
  let timer = null;
  let accepting = false;

  const prefix = () => textarea.value.slice(0, textarea.selectionStart).match(WORD)?.[0] ?? "";

  function hide() {
    clearTimeout(timer);
    asked += 1;
    list.hidden = true;
    names = [];
  }

  async function ask() {
    clearTimeout(timer);
    asked += 1;
    const question = asked;
    const code = textarea.value;
    const offset = textarea.selectionStart;
    const found = await onComplete(code, offset);
    if (question !== asked || textarea.value !== code || textarea.selectionStart !== offset) return;
    const typed = prefix();
    names = found.filter((suggestion) => suggestion.name !== typed);
    chosen = 0;
    if (names.length === 0) {
      list.hidden = true;
      return;
    }
    render();
    place(typed.length);
  }

  function render() {
    list.replaceChildren(
      ...names.map(({ name, kind }, index) => {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(index === chosen));
        const label = document.createElement("span");
        label.textContent = name;
        const what = document.createElement("small");
        what.textContent = kind;
        item.append(label, what);
        // On mousedown, before the textarea loses its focus and the list goes.
        item.addEventListener("mousedown", (event) => {
          event.preventDefault();
          accept(index);
        });
        return item;
      }),
    );
    list.hidden = false;
    // Scrolled by hand: scrollIntoView would also scroll the editor, and the layers under the text with it.
    const item = list.children[chosen];
    if (item.offsetTop < list.scrollTop) list.scrollTop = item.offsetTop;
    else if (item.offsetTop + item.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = item.offsetTop + item.offsetHeight - list.clientHeight;
    }
  }

  /** Puts the list under the start of the word being typed, `typed` characters back; above it near the bottom. */
  function place(typed) {
    const style = getComputedStyle(textarea);
    const measure = document.createElement("canvas").getContext("2d");
    measure.font = `${style.fontSize} ${style.fontFamily}`;
    const width = measure.measureText("M").width;
    const height = Number.parseFloat(style.lineHeight);
    const before = textarea.value.slice(0, textarea.selectionStart);
    const line = before.split("\n").length - 1;
    const column = before.length - before.lastIndexOf("\n") - 1 - typed;
    const x = Number.parseFloat(style.paddingLeft) + column * width - textarea.scrollLeft;
    const below = Number.parseFloat(style.paddingTop) + (line + 1) * height - textarea.scrollTop;
    const room = textarea.clientHeight - below;
    list.style.left = `${Math.max(0, Math.min(x, textarea.clientWidth - list.offsetWidth))}px`;
    list.style.top = `${room >= list.offsetHeight ? below : below - height - list.offsetHeight}px`;
  }

  function accept(index) {
    const { name } = names[index];
    const caret = textarea.selectionStart;
    textarea.setRangeText(name, caret - prefix().length, caret, "end");
    hide();
    accepting = true;
    textarea.dispatchEvent(new Event("input"));
    accepting = false;
  }

  return {
    hide,
    ask,
    /** After an edit: asks again, a moment later, if a name or a dot was just typed. */
    typed() {
      clearTimeout(timer);
      const before = textarea.value.slice(0, textarea.selectionStart);
      if (accepting || textarea.selectionStart !== textarea.selectionEnd || !/(?:[A-Za-z_]\w*|\.)$/.test(before)) {
        hide();
        return;
      }
      timer = setTimeout(ask, WAIT_MS);
    },
    /** Handles a key while the list is open; true if it was the list's. */
    key(event) {
      if (list.hidden || event.ctrlKey || event.metaKey || event.altKey) return false;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        chosen = (chosen + (event.key === "ArrowDown" ? 1 : -1) + names.length) % names.length;
        render();
        return true;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        accept(chosen);
        return true;
      }
      if (event.key === "Escape" || event.key === "ArrowLeft" || event.key === "ArrowRight") hide();
      return event.key === "Escape";
    },
  };
}

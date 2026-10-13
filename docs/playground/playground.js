/*
 * The playground page: an editor, a menu of examples and a worker (worker.js)
 * that runs the program in Pyodide. The page loads nothing heavy by itself:
 * Python is downloaded by the worker, at the first Run.
 *
 * The URL hash selects what the editor opens with: #example=<name> for an
 * example, #code=<base64url> for a shared program.
 */
(() => {
  const base = new URL(".", document.currentScript.src);
  const element = (id) => document.getElementById(id);
  const editor = element("pg-code");
  const menu = element("pg-example");
  const summary = element("pg-summary");
  const runButton = element("pg-run");
  const stopButton = element("pg-stop");
  const shareButton = element("pg-share");
  const status = element("pg-status");
  const output = element("pg-console");
  const images = element("pg-images");
  const INDENT = "    ";
  const highlighted = createHighlightLayer();

  let worker = null;
  let examples = [];
  let imageUrls = [];

  // The code is drawn, highlighted, under a transparent textarea that keeps the
  // caret, the selection and undo. The layer is made of divs, not pre and code,
  // so that Material does not take it for a code block and add a copy button.
  function createHighlightLayer() {
    const layer = document.createElement("div");
    layer.className = "highlight pg-highlight";
    layer.setAttribute("aria-hidden", "true");
    const code = document.createElement("div");
    code.className = "pg-highlight-code";
    layer.append(code);
    editor.before(layer);
    return code;
  }

  function refreshHighlight() {
    // A trailing newline would be invisible in the layer: a space keeps the last line.
    highlighted.innerHTML = `${highlightPython(editor.value)} `;
    syncScroll();
  }

  function syncScroll() {
    // Moved rather than scrolled: the textarea can scroll further, past its scrollbars.
    highlighted.style.transform = `translate(${-editor.scrollLeft}px, ${-editor.scrollTop}px)`;
  }

  function setCode(code) {
    editor.value = code;
    editor.scrollTop = 0;
    editor.scrollLeft = 0;
    refreshHighlight();
  }

  function setRunning(running) {
    runButton.disabled = running;
    stopButton.disabled = !running;
  }

  function write(text, stream) {
    const span = document.createElement("span");
    span.textContent = text;
    if (stream === "stderr") {
      span.className = "pg-stderr";
    }
    output.append(span);
    output.hidden = false;
    output.scrollTop = output.scrollHeight;
  }

  function showImage(name, mime, data) {
    const url = URL.createObjectURL(new Blob([data], { type: mime }));
    imageUrls.push(url);
    const figure = document.createElement("figure");
    const image = document.createElement("img");
    image.src = url;
    image.alt = `${name}, produced by the program`;
    const download = document.createElement("a");
    download.href = url;
    download.download = name;
    download.textContent = `Download ${name}`;
    const caption = document.createElement("figcaption");
    caption.append(download);
    figure.append(image, caption);
    images.append(figure);
  }

  function clearOutput() {
    output.replaceChildren();
    output.hidden = true;
    imageUrls.forEach((url) => URL.revokeObjectURL(url));
    imageUrls = [];
    images.replaceChildren();
  }

  function onMessage(event) {
    const message = event.data;
    switch (message.type) {
      case "status":
        status.textContent = message.text;
        break;
      case "stdout":
      case "stderr":
        write(message.text, message.type);
        break;
      case "image":
        showImage(message.name, message.mime, message.data);
        break;
      case "done":
        status.textContent = message.ok ? "Done." : "The program stopped with an error.";
        setRunning(false);
        break;
      default:
        break;
    }
  }

  function startWorker() {
    worker = new Worker(new URL("worker.js", base));
    worker.onmessage = onMessage;
    worker.onerror = (event) => {
      write(`${event.message}\n`, "stderr");
      status.textContent = "Python could not start: check your connection and run again.";
      worker = null;
      setRunning(false);
    };
  }

  function run() {
    if (runButton.disabled) {
      return;
    }
    clearOutput();
    setRunning(true);
    if (!worker) {
      startWorker();
    }
    worker.postMessage({ type: "run", code: editor.value });
  }

  function stop() {
    // Python cannot be interrupted from outside: the worker goes, and a new one starts at the next run.
    worker?.terminate();
    worker = null;
    setRunning(false);
    status.textContent = "Stopped. Python restarts at the next run, from the browser cache.";
  }

  function encode(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
  }

  function decode(text) {
    const binary = atob(text.replaceAll("-", "+").replaceAll("_", "/"));
    return new TextDecoder().decode(Uint8Array.from(binary, (char) => char.charCodeAt(0)));
  }

  async function share() {
    const url = new URL(window.location.href);
    url.hash = `code=${encode(editor.value)}`;
    history.replaceState(null, "", url);
    try {
      await navigator.clipboard.writeText(url.href);
      status.textContent = "Link to this program copied to the clipboard.";
    } catch {
      status.textContent = "The address bar now holds a link to this program.";
    }
  }

  async function openExample(name) {
    const example = examples.find((candidate) => candidate.name === name) ?? examples[0];
    menu.value = example.name;
    summary.textContent = example.summary ? `${example.title}: ${example.summary}` : example.title;
    const response = await fetch(new URL(`examples/${example.name}.py`, base));
    setCode(await response.text());
    clearOutput();
    status.textContent = "Press Run, or Ctrl+Enter.";
  }

  async function openFromHash() {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    if (!hash.has("code")) {
      await openExample(hash.get("example"));
      return;
    }
    menu.value = "";
    setCode(decode(hash.get("code")));
    summary.textContent = "A shared program.";
    clearOutput();
    status.textContent = "Press Run, or Ctrl+Enter.";
  }

  function onKeyDown(event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      run();
    } else if (event.key === "Tab" && !event.shiftKey) {
      event.preventDefault();
      editor.setRangeText(INDENT, editor.selectionStart, editor.selectionEnd, "end");
      refreshHighlight();
    }
  }

  async function start() {
    const response = await fetch(new URL("manifest.json", base));
    examples = (await response.json()).examples;
    examples.forEach((example) => menu.add(new Option(example.title, example.name)));

    await openFromHash();

    // A link to another example or program, followed from this page, changes only the hash.
    window.addEventListener("hashchange", openFromHash);
    menu.addEventListener("change", () => {
      history.replaceState(null, "", `#example=${menu.value}`);
      openExample(menu.value);
    });
    runButton.addEventListener("click", run);
    stopButton.addEventListener("click", stop);
    shareButton.addEventListener("click", share);
    editor.addEventListener("keydown", onKeyDown);
    editor.addEventListener("input", refreshHighlight);
    editor.addEventListener("scroll", syncScroll);
  }

  start().catch((error) => {
    status.textContent = `The playground could not load its examples: ${error.message}`;
  });
})();

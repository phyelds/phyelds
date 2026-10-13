/*
 * Runs the playground programs in Pyodide, off the main thread, so that a long
 * simulation never freezes the page and Stop can terminate the worker.
 *
 * Messages in:  {type: "run", code}
 * Messages out: {type: "status", text} | {type: "stdout" | "stderr", text}
 *               {type: "image", name, mime, data} | {type: "done", ok}
 */
const PYODIDE_VERSION = "0.28.3";
importScripts(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.js`);

// pandas is left out on purpose: only the CSV exporter needs it, and it weighs 5 MB.
const PACKAGES = ["matplotlib", "pydantic", "wrapt", "pillow"];
const RUN_DIR = "/home/pyodide/run";
const MIME_TYPES = { ".gif": "image/gif", ".png": "image/png" };

// Pyodide reports every package it loads on stdout: keep the console for the program.
const QUIET = { messageCallback: () => {} };

let pyodideReady = null;

function post(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

async function setUp() {
  post("status", { text: "Downloading Python (only the first time, then it is cached)…" });
  const pyodide = await loadPyodide();
  pyodide.setStdout({ batched: (text) => post("stdout", { text: `${text}\n` }) });
  pyodide.setStderr({ batched: (text) => post("stderr", { text: `${text}\n` }) });

  post("status", { text: "Downloading matplotlib and pydantic…" });
  await pyodide.loadPackage(PACKAGES, QUIET);

  post("status", { text: "Installing phyelds…" });
  const sitePackages = pyodide.runPython("import site; site.getsitepackages()[0]");
  const [archive, runner] = await Promise.all([
    fetch("phyelds.zip").then((response) => response.arrayBuffer()),
    fetch("runner.py").then((response) => response.text()),
  ]);
  pyodide.unpackArchive(archive, "zip", { extractDir: sitePackages });
  pyodide.FS.writeFile(`${sitePackages}/playground_runner.py`, runner);
  // The default backend of Pyodide draws on the page, which a worker does not have.
  pyodide.runPython('import matplotlib; matplotlib.use("Agg")');
  return pyodide;
}

async function run(code) {
  pyodideReady ??= setUp();
  const pyodide = await pyodideReady;
  await pyodide.loadPackagesFromImports(code, QUIET);
  if (code.includes("exporter")) {
    await pyodide.loadPackage("pandas", QUIET);
  }

  post("status", { text: "Running…" });
  pyodide.globals.set("user_code", code);
  const result = pyodide.runPython(`
from pathlib import Path
from playground_runner import run_user_code

_result = run_user_code(user_code, Path("${RUN_DIR}"))
(_result.ok, [(output.name, output.data) for output in _result.outputs])
`);
  const [ok, outputs] = result.toJs();
  result.destroy();
  for (const [name, data] of outputs) {
    const mime = MIME_TYPES[name.slice(name.lastIndexOf("."))];
    self.postMessage({ type: "image", name, mime, data }, [data.buffer]);
  }
  return ok;
}

self.onmessage = async (event) => {
  if (event.data.type !== "run") {
    return;
  }
  try {
    post("done", { ok: await run(event.data.code) });
  } catch (error) {
    // Errors of the program are printed by the runner; this is Pyodide itself failing.
    post("stderr", { text: `${error.message ?? error}\n` });
    post("done", { ok: false });
  }
};

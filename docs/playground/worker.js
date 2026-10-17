/*
 * Runs the program of the playground in Pyodide, off the main thread, so that a
 * long round never freezes the page and Stop can terminate the worker. Python is
 * downloaded with the first message; the messages are handled in order.
 *
 * Messages in:  {type: "update", positions, radius, sensors}
 *               {type: "load", code, selections, restart}
 *               {type: "advance", rounds}
 * Messages out: {type: "status", text} | {type: "stdout" | "stderr", text}
 *               {type: "loaded", ok, program, watches}
 *               {type: "snapshot", time, paused, ran, layers} | {type: "failed"}
 */
const PYODIDE_VERSION = "0.28.3";
importScripts(`https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.js`);

const RUN_DIR = "/home/pyodide/run";

// Pyodide reports every package it loads on stdout: keep the console for the program.
const QUIET = { messageCallback: () => {} };

let python = null;
let queue = Promise.resolve();

function post(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

async function setUp() {
  post("status", { text: "Downloading Python (only the first time, then it is cached)…" });
  const pyodide = await loadPyodide();
  pyodide.setStdout({ batched: (text) => post("stdout", { text: `${text}\n` }) });
  pyodide.setStderr({ batched: (text) => post("stderr", { text: `${text}\n` }) });
  // Besides the standard library, the simulator and the libraries of phyelds need only wrapt.
  await pyodide.loadPackage(["wrapt"], QUIET);

  post("status", { text: "Installing phyelds…" });
  const sitePackages = pyodide.runPython("import site; site.getsitepackages()[0]");
  const [archive, runner] = await Promise.all([
    fetch("phyelds.zip").then((response) => response.arrayBuffer()),
    fetch("runner.py").then((response) => response.text()),
  ]);
  pyodide.unpackArchive(archive, "zip", { extractDir: sitePackages });
  pyodide.FS.writeFile(`${sitePackages}/playground_runner.py`, runner);
  const playground = pyodide.runPython(`
from pathlib import Path
from playground_runner import Playground
Playground(Path("${RUN_DIR}"))
`);
  return { pyodide, playground, asdict: pyodide.pyimport("dataclasses").asdict };
}

/** A dataclass of the runner as a plain object, and the Python objects released. */
function plain({ asdict }, result) {
  const dict = asdict(result);
  const value = dict.toJs({ dict_converter: Object.fromEntries });
  dict.destroy();
  result.destroy();
  return value;
}

async function handle(message) {
  python ??= setUp();
  const ready = await python;
  const { pyodide, playground } = ready;
  if (message.type === "update") {
    const positions = pyodide.toPy(message.positions);
    const sensors = pyodide.toPy(message.sensors);
    playground.update(positions, message.radius, sensors);
    positions.destroy();
    sensors.destroy();
  } else if (message.type === "load") {
    await pyodide.loadPackagesFromImports(message.code, QUIET);
    const selections = pyodide.toPy(message.selections);
    post("loaded", plain(ready, playground.load(message.code, selections, message.restart)));
    selections.destroy();
  } else if (message.type === "advance") {
    post("snapshot", plain(ready, playground.advance(message.rounds)));
  }
}

self.onmessage = (event) => {
  queue = queue
    .then(() => handle(event.data))
    .catch((error) => {
      // The errors of the program are printed by the runner: this is Pyodide itself failing.
      post("stderr", { text: `${error.message ?? error}\n` });
      post("failed");
    });
};

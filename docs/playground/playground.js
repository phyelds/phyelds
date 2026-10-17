/*
 * The playground page: the program in an editor on the left, and on the right the
 * network that runs it, in 3D. The page owns the network: where the devices are,
 * how far they hear and what they sense. Python, in a worker (worker.js), runs the
 * program on it round after round and sends back what every device computed, which
 * the stage draws as a stack of layers: the result at the bottom.
 *
 * The URL hash selects what the editor opens with: #example=<name> for an example,
 * #code=<base64url> for a shared program.
 */
import { createMap } from "../walkthrough/map.js";
import { FEWEST, MOST, PLACES, SIZE, createNetwork } from "../walkthrough/model.js";
import { readPalette, toneIndex } from "../walkthrough/palette.js";
import { bindPointer } from "../walkthrough/pointer.js";
import { GAP, PULSE_MS, createScene, reliefOf } from "../walkthrough/scene.js";
import { OFF, ON } from "../walkthrough/views.js";
import { createEditor } from "./editor.js";

const ROUND_MS = 700; // how long a round lasts while playing: every device runs once in it
const MAX_STEP = 0.5; // rounds asked of Python at once at most, so that the devices are seen to run in turn
const EASE_MS = 140; // how fast heights follow a change of value
// Where the first two sensors of a program start: on the source and the target of the walkthrough.
const ANCHORS = [SIZE * SIZE - SIZE - 2, SIZE + 1];
const SENSE = /\bsense\(\s*["']([A-Za-z_]\w*)["']\s*\)/g;
// What the simulator keeps in the data of a device besides its sensors: nothing to switch.
const RESERVED = new Set(["position", "time", "state", "messages", "result", "outputs"]);
const CONSOLE_LINES = 200; // pieces of output the console keeps: a program may print every round
const calm = matchMedia("(prefers-reduced-motion: reduce)");
const element = (id) => document.getElementById(id);
const base = new URL(".", import.meta.url);

const world = {
  places: PLACES.map(({ x, y }) => ({ x, y })), // where each device is
  count: FEWEST,
  sensors: new Map(), // each sensor, and the devices on which it is on
};
const network = createNetwork(world.count, world.places);

const app = {
  playing: true,
  hovered: null,
  selected: 2 * SIZE + 2, // a device in the middle
  palette: readPalette(),
  dirty: true, // the views need drawing again
  panelDirty: true, // the layers, the inspected device and the rounds need writing again
};

// Python, in its worker: the program it runs and its code, the loads it was asked for, and
// whether it is running a step, asked at `asked`.
const python = { worker: null, program: null, code: null, loads: [], stepping: false, asked: 0 };
let snapshot = null; // what the devices computed, as the last step left them
let layers = []; // per layer of the snapshot, the look of every device and the scale
const display = { z: [], ranAt: new Float64Array(MOST).fill(-Infinity) };
let examples = [];

const scene = createScene(element("wt-scene"));
const map = createMap(element("wt-map"));
const editor = createEditor(element("pg-code"), { onRun: run });

const changed = () => {
  app.dirty = true;
};
const inspected = () => app.hovered ?? app.selected;
const escape = (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const format = (number) => String(Number(number.toPrecision(3)));

/** The sensors a program reads, in order: every sense("name") with a name written in it. */
function sensorsOf(code) {
  const names = new Set(Array.from(code.matchAll(SENSE), (match) => match[1]));
  return [...names].filter((name) => !RESERVED.has(name));
}

/** The sensors of the running program that are on at device `id`. */
const rolesOf = (id) => sensorsOf(python.code ?? "").filter((name) => world.sensors.get(name)?.has(id));

// --- Python ---------------------------------------------------------------------------------

function post(message) {
  if (!python.worker) {
    python.worker = new Worker(new URL("worker.js", base));
    python.worker.onmessage = (event) => onMessage(event.data);
    python.worker.onerror = (event) => {
      write(`${event.message}\n`, "stderr");
      stop("Python could not start: check your connection and run again.");
    };
  }
  python.worker.postMessage(message);
}

/** Ends the worker: Python cannot be interrupted from outside. A new one starts at the next run. */
function stop(text) {
  python.worker?.terminate();
  Object.assign(python, { worker: null, program: null, code: null, loads: [], stepping: false });
  setPlaying(false);
  status(text);
}

function sendWorld() {
  post({
    type: "update",
    positions: network.devices.map(({ x, y }) => [x, y]),
    radius: network.range,
    sensors: Object.fromEntries([...world.sensors].map(([name, on]) => [name, [...on]])),
  });
}

/** Loads `code` in Python: from round 0 if `restart`, else on the running devices. */
function load(code, restart) {
  python.loads.push({ code });
  post({ type: "load", code, selections: [], restart });
}

/** Runs the code of the editor from round 0, with its sensors switched on where they start. */
function run() {
  const { code } = editor;
  sensorsOf(code).forEach((name, index) => {
    if (!world.sensors.has(name)) world.sensors.set(name, new Set(ANCHORS.slice(index, index + 1)));
  });
  clearConsole();
  sendWorld();
  load(code, true);
  status("Starting the program…");
}

function restart() {
  if (python.code !== null) load(python.code, true);
}

function onMessage(message) {
  switch (message.type) {
    case "status":
      status(message.text);
      break;
    case "stdout":
    case "stderr":
      write(message.text, message.type);
      break;
    case "loaded":
      onLoaded(message, python.loads.shift());
      break;
    case "snapshot":
      onSnapshot(message);
      break;
    case "failed":
      stop("Python could not start: check your connection and run again.");
      break;
    default:
      break;
  }
}

function onLoaded({ ok, program }, { code }) {
  if (!ok) {
    status(
      python.program
        ? "The program has an error, below: the network goes on with the previous one."
        : "The program has an error, below: fix it and run it again.",
    );
    return;
  }
  Object.assign(python, { program, code });
  if (snapshot) snapshot.paused = false;
  setPlaying(true);
  status(`Every device runs ${program}() once per round.`);
  app.panelDirty = true;
  changed();
}

function onSnapshot(message) {
  python.stepping = false;
  const now = performance.now();
  message.ran.forEach((time, id) => {
    if (Number.isFinite(time) && time !== snapshot?.ran[id]) display.ranAt[id] = now;
  });
  snapshot = message;
  layers = snapshot.layers.map(looksOf);
  if (snapshot.paused && app.playing) {
    setPlaying(false);
    status("A round stopped with an error, below: fix the program and run it again.");
  }
  app.panelDirty = true;
  changed();
}

/** Asks Python for the rounds due since the last step, while playing. */
function askStep(now) {
  if (!python.program || python.stepping || snapshot?.paused) return;
  const rounds = Math.min(MAX_STEP, (now - python.asked) / ROUND_MS);
  if (rounds < 0.01) return;
  python.stepping = true;
  python.asked = now;
  post({ type: "advance", rounds });
}

function stepOnce() {
  setPlaying(false);
  if (!python.program || python.stepping) return;
  python.stepping = true;
  post({ type: "advance", rounds: 1 });
}

// --- What the stage draws -------------------------------------------------------------------

/** How a layer looks: per device a tone and a relief in [0, 1], or null without a value; and its scale. */
function looksOf(layer) {
  const known = layer.numbers.filter(Number.isFinite);
  const low = Math.min(...known);
  const high = Math.max(...known);
  const looks = layer.numbers.map((number) => {
    if (!Number.isFinite(number)) return null;
    if (layer.boolean) return { relief: number, tone: number ? ON : OFF };
    const relief = high > low ? (number - low) / (high - low) : 0.5;
    return { relief, tone: relief };
  });
  return { looks, texts: layer.texts, boolean: layer.boolean, known: known.length > 0, low, high };
}

const layerCount = () => Math.max(1, layers.length);
const focusedLayer = () => layerCount() - 1;
const labelOf = (k) => `${python.program ?? "result"}()`;

/** Moves the heights a step toward the values of the layers; true while anything still moves. */
function ease(elapsed) {
  const count = layerCount();
  const relief = reliefOf(count);
  const pull = calm.matches ? 1 : 1 - Math.exp(-elapsed / EASE_MS);
  display.z.length = count;
  let moving = false;
  for (let k = 0; k < count; k += 1) {
    display.z[k] ??= new Float32Array(MOST).fill(k * GAP);
    const z = display.z[k];
    for (const device of network.devices) {
      const look = layers[k]?.looks[device.id];
      const gap = k * GAP + (look ? look.relief * relief : 0) - z[device.id];
      if (Math.abs(gap) > 1e-3) {
        moving = true;
        z[device.id] += gap * pull;
      }
    }
  }
  return moving;
}

function focusOf(id, k) {
  if (id === null) return null;
  const text = layers[k]?.texts[id];
  const neighbors = network.inRange[id].map((neighbor) => neighbor.id);
  return { id, neighbors, range: false, label: `#${id} · ${text || "no value"}` };
}

function draw(now) {
  const count = layerCount();
  const focused = focusedLayer();
  const hovered = app.hovered;
  const stack = Array.from({ length: count }, (_, k) => ({
    label: labelOf(k),
    focused: k === focused,
    devices: network.devices.map((device) => ({
      id: device.id,
      x: device.x,
      y: device.y,
      z: display.z[k][device.id],
      color: toneIndex(layers[k]?.looks[device.id]?.tone ?? null),
      off: false,
      role: rolesOf(device.id).join(", ") || null,
      ranAt: display.ranAt[device.id],
    })),
    links: network.links.map(({ a, b }) => ({ a, b, style: k === focused ? "plain" : "faint" })),
    highlights:
      k === focused && hovered !== null
        ? network.inRange[hovered].map((neighbor) => ({ a: hovered, b: neighbor.id, style: "neighbor" }))
        : [],
  }));
  const frame = {
    palette: app.palette,
    network,
    layers: stack,
    focus: focusOf(hovered, focused),
    selected: app.selected,
    density: Math.sqrt(FEWEST / network.devices.length),
    now,
    pulses: !calm.matches,
  };
  scene.drawLayers(frame);
  const top = stack[focused];
  map.draw({ ...frame, devices: top.devices, links: top.links, highlights: top.highlights, cloud: null, camera: scene.camera });
  app.dirty = false;
}

// --- The panels -------------------------------------------------------------------------------

function scaleOf(layer) {
  if (!layer?.known) return "";
  const { palette } = app;
  if (layer.boolean) {
    const swatch = (color, label) =>
      `<span class="wt-key"><span class="wt-key-swatch" style="background:${color}"></span>${label}</span>`;
    return `<div class="wt-legend-keys">${swatch(palette.css[palette.on], "True")}${swatch(palette.css[palette.off], "False")}</div>`;
  }
  const stops = Array.from({ length: 9 }, (_, k) => palette.css[toneIndex(k / 8)]).join(", ");
  return (
    `<div class="wt-legend-bar" style="background:linear-gradient(90deg, ${stops})"></div>` +
    `<div class="wt-legend-ends"><span>${format(layer.low)}</span><span>${format(layer.high)}</span></div>`
  );
}

/** The layers, from the top of the stack down, with the values of the inspected device. */
function renderLayers() {
  const id = inspected();
  const rows = [];
  for (let k = layerCount() - 1; k >= 0; k -= 1) {
    const layer = layers[k];
    const focused = k === focusedLayer();
    rows.push(
      `<div class="pg-layer${focused ? " is-focused" : ""}">` +
        `<div class="pg-layer-head"><span class="pg-layer-name">${escape(labelOf(k))}</span>` +
        `<span class="pg-layer-value">${escape(layer?.texts[id] ?? "")}</span></div>` +
        `${focused ? scaleOf(layer) : ""}</div>`,
    );
  }
  element("pg-layers").innerHTML = rows.join("");
}

let deviceKey = null;

/** The inspected device, and a switch for every sensor of the program; rebuilt only when they change. */
function renderDevice() {
  const id = inspected();
  const names = sensorsOf(python.code ?? "");
  const key = `${id}|${names.map((name) => `${name}:${world.sensors.get(name)?.has(id)}`).join(",")}`;
  if (key === deviceKey) return;
  deviceKey = key;
  const neighbours = network.inRange[id].length;
  element("pg-device-name").innerHTML = `<strong>#${id}</strong> · hears ${neighbours} neighbour${neighbours === 1 ? "" : "s"}`;
  element("pg-sensors").replaceChildren(
    ...names.map((name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wt-chip";
      button.textContent = name;
      button.title = `Switch ${name} on or off on #${id}`;
      button.setAttribute("aria-pressed", String(Boolean(world.sensors.get(name)?.has(id))));
      button.addEventListener("click", () => toggleSensor(name, id));
      return button;
    }),
  );
}

function toggleSensor(name, id) {
  const on = world.sensors.get(name) ?? new Set();
  if (on.has(id)) on.delete(id);
  else on.add(id);
  world.sensors.set(name, on);
  sendWorld();
  app.panelDirty = true;
  changed();
}

function setPlaying(playing) {
  app.playing = playing;
  python.asked = performance.now();
  app.panelDirty = true;
}

function refreshPlayer() {
  const play = element("wt-play");
  play.classList.toggle("is-paused", !app.playing);
  play.title = app.playing ? "Pause (Space)" : "Play (Space)";
  play.setAttribute("aria-label", app.playing ? "Pause" : "Play");
  const round = snapshot ? Math.floor(snapshot.time + 1e-9) : 0;
  let state = "not started";
  if (snapshot?.paused) state = "stopped by an error";
  else if (python.program) state = app.playing ? "running" : "paused";
  const live = app.playing && state === "running";
  element("wt-round").innerHTML =
    `<span class="wt-status${live ? "" : " is-stable"}"></span>round <strong>${round}</strong> · ${state}`;
}

function status(text) {
  element("pg-status").textContent = text;
}

function write(text, stream) {
  const output = element("pg-console");
  const piece = document.createElement("span");
  piece.textContent = text;
  if (stream === "stderr") piece.className = "pg-stderr";
  output.append(piece);
  while (output.childElementCount > CONSOLE_LINES) output.firstElementChild.remove();
  output.hidden = false;
  output.scrollTop = output.scrollHeight;
}

function clearConsole() {
  const output = element("pg-console");
  output.replaceChildren();
  output.hidden = true;
}

// --- Examples and links ---------------------------------------------------------------------

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
  url.hash = `code=${encode(editor.code)}`;
  history.replaceState(null, "", url);
  try {
    await navigator.clipboard.writeText(url.href);
    status("Link to this program copied to the clipboard.");
  } catch {
    status("The address bar now holds a link to this program.");
  }
}

async function openExample(name) {
  const example = examples.find((candidate) => candidate.name === name) ?? examples[0];
  element("pg-example").value = example.name;
  element("pg-summary").textContent = example.summary.replace(/^./, (first) => first.toUpperCase());
  const response = await fetch(new URL(`examples/${example.name}.py`, base));
  editor.setCode(await response.text());
  run();
}

async function openFromHash() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  if (!hash.has("code")) {
    await openExample(hash.get("example"));
    return;
  }
  element("pg-example").value = "";
  element("pg-summary").textContent = "A shared program.";
  editor.setCode(decode(hash.get("code")));
  run();
}

// --- Pointer, keyboard and controls ---------------------------------------------------------

function hover(id) {
  if (app.hovered === id) return;
  app.hovered = id;
  app.panelDirty = true;
  changed();
}

function select(id) {
  app.selected = id;
  app.panelDirty = true;
  changed();
}

bindPointer(element("wt-scene"), {
  pick: scene.pick,
  grab: () => null,
  drag: () => {},
  orbit: (dx, dy) => {
    scene.orbit(dx, dy);
    changed();
  },
  hover,
  select,
});
bindPointer(element("wt-map"), { pick: map.pick, grab: () => null, drag: () => {}, hover, select });

element("wt-scene").addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    scene.zoom(Math.exp(-event.deltaY * 0.0015));
    changed();
  },
  { passive: false },
);

element("pg-run").addEventListener("click", run);
element("pg-stop").addEventListener("click", () => stop("Stopped. Python starts again at the next run."));
element("pg-share").addEventListener("click", share);
element("wt-play").addEventListener("click", () => setPlaying(!app.playing));
element("wt-round-step").addEventListener("click", stepOnce);
element("wt-restart").addEventListener("click", restart);
element("wt-home").addEventListener("click", () => {
  scene.reset();
  changed();
});

document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey || event.target.closest("input, select, textarea")) return;
  const onControl = event.target.closest("button, [role=button], a");
  if (event.key === " " && !onControl) {
    event.preventDefault();
    setPlaying(!app.playing);
  } else if (event.key === ".") {
    stepOnce();
  } else if (event.key === "r" || event.key === "R") {
    restart();
  }
});

window.addEventListener("themechange", () => {
  app.palette = readPalette();
  app.panelDirty = true;
  changed();
});

const resize = () => {
  scene.resize();
  map.resize();
  changed();
};
new ResizeObserver(resize).observe(element("wt-stage"));

let lastFrame = performance.now();

function frame(now) {
  const elapsed = Math.min(64, now - lastFrame);
  lastFrame = now;
  if (app.playing) askStep(now);
  if (app.panelDirty) {
    renderLayers();
    renderDevice();
    refreshPlayer();
    app.panelDirty = false;
  }
  const pulsing = network.devices.some((device) => now - display.ranAt[device.id] < PULSE_MS);
  if (ease(elapsed) || app.dirty || pulsing) draw(now);
  requestAnimationFrame(frame);
}

async function start() {
  const response = await fetch(new URL("manifest.json", base));
  examples = (await response.json()).examples;
  for (const example of examples) element("pg-example").add(new Option(example.title, example.name));
  await openFromHash();
  // A link to another example or program, followed from this page, changes only the hash.
  window.addEventListener("hashchange", openFromHash);
  element("pg-example").addEventListener("change", (event) => {
    history.replaceState(null, "", `#example=${event.target.value}`);
    openExample(event.target.value);
  });
}

resize();
requestAnimationFrame(frame);
start().catch((error) => {
  status(`The playground could not load its examples: ${error.message}`);
});

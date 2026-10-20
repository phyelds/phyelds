/*
 * The playground page: the program in an editor on the left, and on the right the
 * network that runs it, in 3D. The page owns the network: where the devices are,
 * how far they hear and what they sense. Python, in a worker (worker.js), runs the
 * program on it round after round and sends back what every device computed, which
 * the stage draws as a stack of layers: the result at the bottom, and above it every
 * expression of the program that the reader selects and watches. A program that sends a
 * velocity moves its devices: Python moves them, and the page draws them where they are.
 *
 * The URL hash selects what the editor opens with: #example=<name> for an example,
 * #code=<base64url> for a shared program.
 */
import { createMap } from "../walkthrough/map.js";
import { FEWEST, MOST, PLACES, SPAN, createNetwork } from "../walkthrough/model.js";
import { readPalette } from "../walkthrough/palette.js";
import { bindPointer } from "../walkthrough/pointer.js";
import { LIFT, PULSE_MS, createScene } from "../walkthrough/scene.js";
import { MAPS, categoryOf, extendPalette, namedOf, stopsOf, toneOf } from "./colours.js";
import { createEditor, shifted } from "./editor.js";
import { createMenu } from "./menu.js";

const ROUND_MS = 700; // how long a round lasts while playing: every device runs once in it
const MAX_STEP = 0.5; // rounds asked of Python at once at most, so that the devices are seen to run in turn
const EASE_MS = 140; // how fast heights follow a change of value
const WORLD_MARGIN = 2.5; // how far beyond the arena devices move: WORLD in runner.py
const GLIDE_MS = 90; // how fast a drawn device follows its device, which Python moves step by step
const FEWEST_DEVICES = 2;
// Where the first two sensors of a program start: by the source and the target of the walkthrough.
const ANCHORS = [
  { x: SPAN - 1, y: SPAN - 1 },
  { x: 1, y: 1 },
];
// A sensor read with sense("name"), or named with Sensor("name").
const SENSE = /\b(?:sense|Sensor)\(\s*["']([A-Za-z_]\w*)["']\s*\)/g;
// What the simulator keeps in the data of a device besides its sensors: nothing to switch.
const RESERVED = new Set(["position", "time", "state", "messages", "result", "outputs"]);
const CONSOLE_LINES = 200; // pieces of output the console keeps: a program may print every round
const MAX_WATCHES = 4; // expressions watched at once: past five layers, the stack is hard to read
// From straight above, north up: the plane is level with the screen. A pitch of exactly a right
// angle would leave the camera no direction to its right.
const ABOVE = { yaw: -Math.PI / 2, pitch: Math.PI / 2 - 1e-3, zoom: 1.1 };
const calm = matchMedia("(prefers-reduced-motion: reduce)");
const element = (id) => document.getElementById(id);
const base = new URL(".", import.meta.url);

/**
 * The places of the walkthrough in an order whose every beginning is spread over the arena:
 * the one nearest the centre first, then each time the farthest from those before it. A
 * network of any size is then the first places, and adding devices never moves the others.
 */
function spread(places) {
  const left = places.map(({ x, y }) => ({ x, y }));
  // How far each place left is from those taken; at first, closer to the centre is better.
  let gaps = left.map(({ x, y }) => -Math.hypot(x - SPAN / 2, y - SPAN / 2));
  const taken = [];
  while (left.length > 0) {
    const best = gaps.indexOf(Math.max(...gaps));
    const [place] = left.splice(best, 1);
    gaps.splice(best, 1);
    gaps = gaps.map((gap, index) => Math.min(taken.length === 0 ? Infinity : gap, Math.hypot(left[index].x - place.x, left[index].y - place.y)));
    taken.push(place);
  }
  return taken;
}

const world = {
  places: spread(PLACES), // where each device is, as the reader placed it
  moved: [], // where each device is, as its program moved it: the places of the last step
  ranges: [], // how far each device hears, as its range adapted: the ranges of the last step
  count: FEWEST,
  radius: null, // how far devices hear, if the reader chose it; else it follows their number
  sensors: new Map(), // each sensor, and the devices on which it is on
  dirty: false, // Python has not been told yet
};
/** Where the devices are: where their program moved them, else where the reader placed them. */
const placesNow = () => world.places.map((place, id) => world.moved[id] ?? place);
const connect = () => createNetwork(world.count, placesNow(), world.radius ?? undefined, world.ranges);
let network = connect();

const app = {
  playing: true,
  hovered: null,
  selected: 0, // the device nearest the centre
  speed: 1, // rounds per ROUND_MS
  focus: 0, // the layer in front, which the map shows: 0 is the result, k the k-th watch
  palette: extendPalette(readPalette()),
  look: { map: "plasma", height: 1, visible: true }, // how the result is drawn: colours, height, whether at all
  solo: false, // only the layer in front is shown
  flat: false, // the layer in front, from above and flat; the camera of the 3D view is kept in `turned`
  moved: false, // the program of this run moved its devices: the view went flat and wide for it
  layout: "both", // what the page shows: the program ("code"), the network ("network"), or both
  turned: null,
  dirty: true, // the views need drawing again
  panelDirty: true, // the layers, the inspected device and the rounds need writing again
};

// Python, in its worker: the program it runs and its code, the loads it was asked for, and
// whether it is running a step, asked at `asked`.
const python = { worker: null, program: null, code: null, shape: null, loads: [], stepping: false, asked: 0 };
let snapshot = null; // what the devices computed, as the last step left them
let layers = []; // per layer of the snapshot, the look of every device and the scale
// The watched expressions: where they are in the code Python runs, their label, how they are
// drawn, and where the editor marks them, which edits move (null once an edit went through one).
let watches = [];
// Where the devices are drawn, and the heights of their layers: they follow the devices smoothly.
const display = {
  x: new Float64Array(MOST).fill(NaN),
  y: new Float64Array(MOST).fill(NaN),
  z: [],
  ranAt: new Float64Array(MOST).fill(-Infinity),
};
let examples = [];

const scene = createScene(element("wt-scene"));
const map = createMap(element("wt-map"));
const editor = createEditor(element("pg-code"), { onRun: run, onWatch: watch, onEdit, onComplete: complete });
const menu = createMenu(
  {
    button: element("pg-example"),
    title: element("pg-example-title"),
    panel: element("pg-menu"),
    search: element("pg-search"),
    list: element("pg-menu-list"),
  },
  {
    onPick: (name) => {
      history.replaceState(null, "", `#example=${name}`);
      openExample(name);
    },
  },
);
const completions = new Map(); // what the editor asked Python to complete, by id, waiting for the answer
let questions = 0;

const changed = () => {
  app.dirty = true;
};
const inspected = () => app.hovered ?? app.selected;
const format = (number) => String(Number(number.toPrecision(3)));

/** The sensors a program reads, in order: every sense("name") or Sensor("name") with a name written in it. */
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
  for (const answer of completions.values()) answer([]);
  completions.clear();
  Object.assign(python, { worker: null, program: null, code: null, shape: null, loads: [], stepping: false });
  setPlaying(false);
  status(text);
}

function sendWorld() {
  post({
    type: "update",
    positions: world.places.slice(0, world.count).map(({ x, y }) => [x, y]),
    radius: network.range,
    sensors: Object.fromEntries([...world.sensors].map(([name, on]) => [name, [...on]])),
  });
}

/**
 * Loads `code` in Python, watching the expressions under `selections`: from round 0 if
 * `restart`, else on the running devices. `previous` are the watches the selections come
 * from, whose names and looks they keep, null for a new one; `reason` says what to tell
 * the reader.
 */
function load(code, selections, restart, reason, previous = selections.map(() => null)) {
  python.loads.push({ code, restart, reason, previous });
  post({ type: "load", code, selections, restart });
}

/** The names that complete `code` at `offset`, as Python finds them. */
function complete(code, offset) {
  questions += 1;
  const id = questions;
  post({ type: "complete", id, code, offset });
  return new Promise((answer) => completions.set(id, answer));
}

/** Where the watches are in the code Python runs. */
const spans = (list = watches) => list.map(({ start, end }) => [start, end]);

/** The watches that edits left in the editor. */
const kept = () => watches.filter((each) => each.mark);
const marked = () => kept().map(({ mark }) => [mark.start, mark.end]);

/** The device nearest `point`, among the first `count`. */
function nearest(point, count = world.count) {
  const places = placesNow();
  const distance = (id) => Math.hypot(places[id].x - point.x, places[id].y - point.y);
  let best = 0;
  for (let id = 1; id < count; id += 1) {
    if (distance(id) < distance(best)) best = id;
  }
  return best;
}

/** Runs the code of the editor from round 0, with its sensors switched on where they start. */
function run() {
  const { code } = editor;
  sensorsOf(code).forEach((name, index) => {
    if (!world.sensors.has(name)) world.sensors.set(name, new Set(index < ANCHORS.length ? [nearest(ANCHORS[index])] : []));
  });
  clearConsole();
  app.moved = false;
  sendWorld();
  load(code, marked(), true, "run", kept());
  status("Starting the program…");
}

function restart() {
  if (python.code !== null) load(python.code, spans(), true, "run", watches);
}

/** Watches the expression under the selection: on the running devices, if they run the code of the editor. */
function watch() {
  if (watches.length >= MAX_WATCHES) {
    status(`At most ${MAX_WATCHES} expressions are watched at once: remove one first, with ×.`);
    return;
  }
  const { code } = editor;
  const same = code === python.code;
  const old = same ? watches : kept();
  load(code, [...(same ? spans() : marked()), editor.selection()], !same, "watch", [...old, null]);
}

function unwatch(index) {
  const others = watches.filter((_, k) => k !== index);
  load(python.code, spans(others), false, "unwatch", others);
}

/** Moves the marks of the watches with the edits of the code. */
function onEdit(change) {
  for (const each of watches) {
    if (each.mark) each.mark = shifted(each.mark, change);
  }
  renderMarks();
  if (editor.code !== python.code) status("Edited: Run (Ctrl+Enter) applies the code and starts the devices over.");
}

function renderMarks() {
  editor.setMarks(watches.flatMap((each, k) => (each.mark ? [{ ...each.mark, focused: k + 1 === focusedLayer() }] : [])));
}

/**
 * Brings layer `k` to the front and selects its expression in the editor if `select`. A
 * hidden layer brought to the front shows again, unless layers are shown one at a time.
 */
function focusLayer(k, select = true) {
  app.focus = k;
  if (!oneAtATime()) lookOf(k).visible = true;
  const mark = watches[k - 1]?.mark;
  if (mark && select) editor.select(mark.start, mark.end);
  renderMarks();
  app.panelDirty = true;
  changed();
}

/** Moves the front one layer up (-1) or down (+1) the stack: through every layer one at a time, else the shown ones. */
function moveFocus(direction) {
  const candidates = stackOrder().filter((k) => oneAtATime() || lookOf(k).visible);
  const next = candidates[candidates.indexOf(focusedLayer()) + direction];
  if (next !== undefined) focusLayer(next, false);
}

/** Moves watch layer `k` up (-1) or down (+1) among the watches; the result stays on top. */
function moveWatch(k, step) {
  if (k === 0) return;
  const watched = stackOrder().slice(1);
  const other = watched[watched.indexOf(k) + step];
  if (other === undefined) return;
  [lookOf(k).rank, lookOf(other).rank] = [lookOf(other).rank, lookOf(k).rank];
  app.panelDirty = true;
  changed();
}

/** Hides layer `k`, or shows it again; one layer stays shown, and the front moves off a hidden one. */
function toggleShown(k) {
  const look = lookOf(k);
  if (!look.visible) {
    look.visible = true;
  } else {
    const others = allLayers().filter((other) => other !== k && lookOf(other).visible);
    if (others.length === 0) return;
    look.visible = false;
    if (focusedLayer() === k) app.focus = others.filter((other) => other < k).pop() ?? others[0];
  }
  renderMarks();
  app.panelDirty = true;
  changed();
}

function setSolo(solo) {
  app.solo = solo;
  // Back to the stack, the layer the reader was looking at stays in view.
  if (!oneAtATime()) lookOf(focusedLayer()).visible = true;
  element("pg-solo").setAttribute("aria-pressed", String(solo));
  app.panelDirty = true;
  changed();
}

/** Looks at the layer in front from above, flat, or back at the stack in 3D, as the camera left it. */
const LAYOUTS = ["code", "both", "network"];

function setLayout(layout) {
  if (!LAYOUTS.includes(layout)) return;
  app.layout = layout;
  element("pg-layout").closest(".pg").dataset.layout = layout;
  for (const button of element("pg-layout").querySelectorAll("button")) {
    button.setAttribute("aria-checked", String(button.dataset.show === layout));
  }
}

function setFlat(flat) {
  if (flat === app.flat) return;
  app.flat = flat;
  if (flat) {
    app.turned = { ...scene.camera };
    Object.assign(scene.camera, ABOVE);
  } else {
    Object.assign(scene.camera, app.turned);
    if (!oneAtATime()) lookOf(focusedLayer()).visible = true;
  }
  element("pg-flat").setAttribute("aria-pressed", String(flat));
  element("wt-stage").classList.toggle("is-flat", flat);
  element("pg-hint").textContent = flat
    ? "Drag a device to move it · scroll to zoom"
    : "Drag a device to move it · drag elsewhere to orbit · scroll to zoom";
  app.panelDirty = true;
  changed();
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
    case "completions":
      completions.get(message.id)?.(message.suggestions);
      completions.delete(message.id);
      break;
    case "failed":
      stop("Python could not start: check your connection and run again.");
      break;
    default:
      break;
  }
}

function onLoaded({ ok, program, watches: watched, shape }, { code, restart, reason, previous }) {
  if (!ok) {
    const what = reason === "watch" ? "That cannot be watched" : "The program has an error";
    const then = python.program ? "the network goes on as it was" : "fix it and run it again";
    status(`${what}, as the console says: ${then}.`);
    return;
  }
  const marks = new Map(watches.map((each) => [`${each.start}:${each.end}`, each.mark]));
  const same = editor.code === code;
  // A watch keeps its name and its look: Python names it after the expression, the reader may
  // have picked a variable.
  watches = watched.map(({ start, end, label }, k) => ({
    start,
    end,
    label: previous[k]?.label ?? label,
    look: previous[k]?.look ?? defaultLook(),
    mark: same ? { start, end } : (marks.get(`${start}:${end}`) ?? null),
  }));
  // A new watch goes right under the result; the others keep their places.
  for (const each of watches) {
    if (each.look.rank === undefined) each.look.rank = Math.min(0, ...watches.map((other) => other.look.rank ?? 0)) - 1;
  }
  app.focus = reason === "watch" ? watches.length : Math.min(app.focus, watches.length);
  // The shape the program defines, if any, drawn under the result as the ground the swarm takes.
  Object.assign(python, { program, code, shape });
  if (snapshot) {
    // The values of the old watches are not those of the new ones: they come back as the devices run.
    snapshot.paused = false;
    snapshot.layers = snapshot.layers.slice(0, 1);
  }
  refreshLooks();
  renderMarks();
  if (reason === "watch") status(`Watching ${watches.at(-1).label} on every device: its layer is under the result.`);
  else status(`Every device runs ${program}() once per round. Select an expression and Watch it.`);
  // A watch added to a paused network shows up after one round, which is when the devices compute it.
  if (restart) setPlaying(true);
  else if (!app.playing) stepOnce();
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
  followDevices(message.positions, message.ranges);
  refreshLooks();
  if (snapshot.paused && app.playing) {
    setPlaying(false);
    status("A round stopped with an error, below: fix the program and run it again.");
  }
  app.panelDirty = true;
  changed();
}

/** Draws the devices where their program moved them, linked as their ranges say, if either changed. */
function followDevices(positions, ranges) {
  const moved = positions.map(([x, y]) => ({ x, y }));
  const same =
    moved.length === world.moved.length &&
    moved.every(({ x, y }, id) => x === world.moved[id].x && y === world.moved[id].y) &&
    ranges.every((range, id) => range === world.ranges[id]);
  if (same) return;
  world.moved = moved;
  world.ranges = ranges;
  // A swarm moves in a wider world, seen from above unless layers are watched under it:
  // once a run, when its devices start moving.
  if (!app.moved && moved.some(({ x, y }, id) => x !== world.places[id].x || y !== world.places[id].y)) {
    app.moved = true;
    if (watches.length === 0) setFlat(true);
    else changed();
  }
  network = connect();
  app.panelDirty = true;
}

/** Asks Python for the rounds due since the last step, while playing. */
function askStep(now) {
  if (!python.program || python.stepping || snapshot?.paused) return;
  const rounds = Math.min(MAX_STEP, ((now - python.asked) * app.speed) / ROUND_MS);
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

const RELIEF = 1.0; // world height of a value of 1 at height 1×, in a stack of layers
const MARGIN = 0.4; // world height between the highest value of a layer and the plane above it
const HIGHEST = 3; // how many times its usual height a layer rises at most
const defaultLook = () => ({ map: "plasma", height: 1, visible: true });
const allLayers = () => Array.from({ length: layerCount() }, (_, k) => k);

const layerCount = () => 1 + watches.length;
const focusedLayer = () => Math.min(app.focus, layerCount() - 1);
const labelOf = (k) => (k === 0 ? `${python.program ?? "result"}()` : watches[k - 1].label);
const lookOf = (k) => (k === 0 ? app.look : watches[k - 1]?.look);
const oneAtATime = () => app.solo || app.flat;
const isShown = (k) => (oneAtATime() ? k === focusedLayer() : lookOf(k).visible);
/** The layers from the top of the stack down: the result, then the watches in the order the reader gave them. */
const stackOrder = () => [0, ...allLayers().slice(1).sort((a, b) => lookOf(a).rank - lookOf(b).rank)];

/**
 * How a layer looks: per device a colour and a relief in [0, 1], or null without a
 * value; and its scale. Booleans are True and False; categories give every value a
 * colour of its own; other values go along the colour map, from the lowest to the highest.
 */
function looksOf(layer, look) {
  const { palette } = app;
  const known = layer.numbers.filter(Number.isFinite);
  // The scale Python keeps, which only widens in a run, so that a colour keeps its meaning.
  const low = Number.isFinite(layer.low) ? layer.low : Math.min(...known);
  const high = Number.isFinite(layer.high) ? layer.high : Math.max(...known);
  const share = (number) => (high > low ? (number - low) / (high - low) : 0.5);
  const looks = layer.numbers.map((number, id) => {
    const finite = Number.isFinite(number);
    if (layer.boolean) return finite ? { relief: number, colour: number ? palette.on : palette.off } : null;
    // A value named after a colour, as Light.GREEN, is drawn in it, whatever the map.
    const named = layer.colours?.[id] ? namedOf(palette, layer.colours[id]) : null;
    if (named !== null) return { relief: finite ? share(number) : 0, colour: named };
    // A heading, in degrees from east: a colour of the wheel, flat, as a swarm moves on a plane.
    if (layer.direction) {
      const heading = (number * Math.PI) / 180;
      return finite ? { relief: 0, colour: toneOf(palette, "directions", (number + 180) / 360), heading } : null;
    }
    if (look.map === "categories") {
      return layer.texts[id] ? { relief: finite ? share(number) : 0, colour: categoryOf(palette, number, layer.texts[id]) } : null;
    }
    return finite ? { relief: share(number), colour: toneOf(palette, look.map, share(number)) } : null;
  });
  const map = layer.direction ? "directions" : look.map;
  const { texts, boolean, direction, colours, keys } = layer;
  return { looks, texts, boolean, direction, colours, keys, known: known.length > 0, low, high, map };
}

/** The looks of the layers of the last step, as the reader set them. */
function refreshLooks() {
  layers = snapshot ? snapshot.layers.map((layer, k) => looksOf(layer, lookOf(k) ?? defaultLook())) : [];
}

/**
 * The layers of the stack, bottom up: each with the height of its plane and of a value of
 * 1 in it. A layer alone rises as in the walkthrough; in a stack, each rises as high as the
 * reader set it, and the next plane comes after its highest value.
 */
function stackOf() {
  const shown = stackOrder().reverse().filter(isShown);
  let unit = shown.length === 1 ? LIFT : RELIEF;
  if (app.flat) unit = 0;
  let base = 0;
  return shown.map((k) => {
    const relief = unit * lookOf(k).height;
    const layer = { k, base, relief };
    base += relief + MARGIN;
    return layer;
  });
}

/** Moves the drawn devices a step toward their devices; true while any still moves. */
function glide(elapsed) {
  const pull = calm.matches ? 1 : 1 - Math.exp(-elapsed / GLIDE_MS);
  let moving = false;
  for (const { id, x, y } of network.devices) {
    const gaps = [x - display.x[id], y - display.y[id]];
    if (gaps.some(Number.isNaN)) {
      display.x[id] = x;
      display.y[id] = y;
    } else if (Math.abs(gaps[0]) + Math.abs(gaps[1]) > 1e-4) {
      moving = true;
      display.x[id] += gaps[0] * pull;
      display.y[id] += gaps[1] * pull;
    }
  }
  return moving;
}

/** Moves the heights a step toward the values of the layers; true while anything still moves. */
function ease(elapsed) {
  const pull = calm.matches ? 1 : 1 - Math.exp(-elapsed / EASE_MS);
  let moving = glide(elapsed);
  display.z.length = layerCount();
  for (const { k, base, relief } of stackOf()) {
    display.z[k] ??= new Float32Array(MOST).fill(base);
    const z = display.z[k];
    for (const device of network.devices) {
      const look = layers[k]?.looks[device.id];
      const gap = base + (look ? look.relief * relief : 0) - z[device.id];
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
  const focused = focusedLayer();
  const hovered = app.hovered;
  const stack = stackOf();
  const drawn = stack.map(({ k, base }) => ({
    base,
    label: labelOf(k),
    focused: k === focused,
    devices: network.devices.map((device) => ({
      id: device.id,
      x: display.x[device.id],
      y: display.y[device.id],
      z: display.z[k][device.id],
      color: layers[k]?.looks[device.id]?.colour ?? null,
      heading: layers[k]?.looks[device.id]?.heading ?? null, // drawn as an arrow, when the value is a heading
      off: false,
      role: rolesOf(device.id).join(", ") || null,
      ranAt: display.ranAt[device.id],
    })),
    links: network.links.map(({ a, b }) => ({ a, b, style: k === focused ? "plain" : "faint" })),
    shape: k === 0 ? python.shape : null,
    highlights:
      k === focused && hovered !== null
        ? network.inRange[hovered].map((neighbor) => ({ a: hovered, b: neighbor.id, style: "neighbor" }))
        : [],
  }));
  const highest = stack[stack.length - 1];
  const frame = {
    // A swarm moves in a world wider than the arena, which the views show whole.
    margin: app.moved ? WORLD_MARGIN : 0,
    palette: app.palette,
    network,
    layers: drawn,
    top: highest.base + highest.relief,
    focus: focusOf(hovered, focused),
    selected: app.selected,
    // Few devices are drawn larger, up to a point: two would fill the arena.
    density: Math.min(1.5, Math.sqrt(FEWEST / network.devices.length)),
    now,
    pulses: !calm.matches,
  };
  scene.drawLayers(frame);
  const front = drawn.find((layer) => layer.focused) ?? drawn[drawn.length - 1];
  map.draw({ ...frame, devices: front.devices, links: front.links, highlights: front.highlights, cloud: null, camera: scene.camera, shape: python.shape });
  app.dirty = false;
}

// --- The panels -------------------------------------------------------------------------------

function scaleOf(layer) {
  if (!layer) return "";
  const { palette } = app;
  const swatch = (colour, label = "") =>
    `<span class="wt-key"><span class="wt-key-swatch" style="background:${colour}"></span>${label}</span>`;
  if (layer.boolean) {
    return `<div class="wt-legend-keys">${swatch(palette.css[palette.on], "True")}${swatch(palette.css[palette.off], "False")}</div>`;
  }
  // An enum: a key for each of its members, shown by the devices or not, in the colour it is
  // named after or else in its tone of the map.
  if (layer.keys?.length > 0) {
    const share = (number) => (layer.high > layer.low ? (number - layer.low) / (layer.high - layer.low) : 0.5);
    const toned = (text, number) =>
      layer.map === "categories" ? categoryOf(palette, number, text) : toneOf(palette, layer.map, share(number));
    const colourOf = ([text, name, number]) => namedOf(palette, name) ?? toned(text, number);
    return `<div class="wt-legend-keys">${layer.keys.map((key) => swatch(palette.css[colourOf(key)], key[0])).join("")}</div>`;
  }
  if (layer.direction) {
    return (
      `<div class="wt-legend-bar" style="background:linear-gradient(90deg, ${stopsOf(palette, "directions").join(", ")})"></div>` +
      `<div class="wt-legend-ends"><span>W</span><span>S</span><span>E</span><span>N</span><span>W</span></div>`
    );
  }
  if (layer.map === "categories") {
    return `<div class="pg-categories">${stopsOf(palette, "categories").map((colour) => swatch(colour)).join("")}</div>`;
  }
  if (!layer.known) return "";
  return (
    `<div class="wt-legend-bar" style="background:linear-gradient(90deg, ${stopsOf(palette, layer.map).join(", ")})"></div>` +
    `<div class="wt-legend-ends"><span>${format(layer.low)}</span><span>${format(layer.high)}</span></div>`
  );
}

function setLook(k, change) {
  Object.assign(lookOf(k), change);
  refreshLooks();
  app.panelDirty = true;
  changed();
}

/** Whether some value of the layer is drawn in the colour it is named after. */
const hasNamedColours = (layer) => Boolean(layer?.colours?.some((name) => name && namedOf(app.palette, name) !== null));

/** The colour map and the height of layer `k`, which the reader sets on its row, when it is in front. */
function lookControls(k) {
  const look = lookOf(k);
  const controls = document.createElement("div");
  controls.className = "pg-look";
  // Headings have a wheel of their own, and stay flat.
  if (layers[k]?.direction) return controls;
  // Booleans and values named after colours have colours of their own: no map to pick.
  if (!layers[k]?.boolean && !hasNamedColours(layers[k])) {
    const colours = document.createElement("select");
    colours.title = "Colours of this layer";
    colours.setAttribute("aria-label", `Colours of ${labelOf(k)}`);
    for (const name of MAPS) colours.add(new Option(name, name, false, name === look.map));
    colours.addEventListener("change", () => setLook(k, { map: colours.value }));
    controls.append(colours);
  }
  const height = document.createElement("label");
  height.className = "pg-height";
  height.title = "How high the values of this layer rise";
  const slider = Object.assign(document.createElement("input"), { type: "range", min: 0, max: HIGHEST, step: 0.1 });
  slider.value = look.height;
  const shown = document.createElement("output");
  shown.textContent = `${look.height.toFixed(1)}×`;
  slider.addEventListener("input", () => {
    shown.textContent = `${Number(slider.value).toFixed(1)}×`;
    setLook(k, { height: Number(slider.value) });
  });
  height.append("height", slider, shown);
  controls.append(height);
  return controls;
}

let layerRows = null; // the rows of the list of the layers, and the layers they were built for
const EYE =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="8" cy="8" r="1.9" fill="currentColor"/></svg>';
const UP =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 10l4-4 4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const DOWN =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const EYE_SHUT =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2.5 13.5l11-11" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>';

/** The layers, from the top of the stack down, with the values of the inspected device. */
function renderLayers() {
  const focused = focusedLayer();
  const labels = stackOrder().map((k) => `${isShown(k)}:${labelOf(k)}`);
  const kind = [layers[focused]?.boolean, layers[focused]?.direction, hasNamedColours(layers[focused])].map(Boolean);
  const key = [focused, oneAtATime(), ...kind, ...labels].join("\n");
  // Rebuilt only when the layers change, not at every step: a click must find its button.
  if (layerRows?.key !== key) layerRows = { key, rows: buildLayerRows(focused) };
  const id = inspected();
  for (const { k, value, scale } of layerRows.rows) {
    value.textContent = layers[k]?.texts[id] ?? "";
    if (scale) scale.innerHTML = scaleOf(layers[k]);
  }
}

/** A button of a row that moves its watch, `icon` pointing where. */
function arrow(icon, title, label, disabled, move) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pg-layer-move";
  button.innerHTML = icon;
  button.title = title;
  button.disabled = disabled;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", move);
  return button;
}

function buildLayerRows(focused) {
  const list = element("pg-layers");
  const rows = [];
  const watched = stackOrder().slice(1);
  list.replaceChildren();
  for (const k of stackOrder()) {
    const row = document.createElement("div");
    row.className = `pg-layer${k === focused ? " is-focused" : ""}${isShown(k) ? "" : " is-hidden"}`;
    const head = document.createElement("div");
    head.className = "pg-layer-head";
    const eye = document.createElement("button");
    eye.type = "button";
    eye.className = "pg-layer-eye";
    eye.innerHTML = lookOf(k).visible ? EYE : EYE_SHUT;
    eye.title = lookOf(k).visible ? "Hide this layer" : "Show this layer";
    eye.setAttribute("aria-label", `${lookOf(k).visible ? "Hide" : "Show"} ${labelOf(k)}`);
    eye.setAttribute("aria-pressed", String(!lookOf(k).visible));
    eye.addEventListener("click", () => toggleShown(k));
    head.append(eye);
    const name = document.createElement("button");
    name.type = "button";
    name.className = "pg-layer-name";
    name.textContent = labelOf(k);
    name.title = k === 0 ? "Bring the result to the front" : "Bring this layer to the front, and select its expression";
    name.addEventListener("click", () => focusLayer(k));
    const value = document.createElement("span");
    value.className = "pg-layer-value";
    head.append(name, value);
    if (k > 0) {
      const position = watched.indexOf(k);
      head.append(
        arrow(UP, "Move up the stack (Shift+↑ when in front)", `Move ${labelOf(k)} up`, position === 0, () => moveWatch(k, -1)),
        arrow(DOWN, "Move down the stack (Shift+↓ when in front)", `Move ${labelOf(k)} down`, position === watched.length - 1, () => moveWatch(k, 1)),
      );
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "pg-layer-remove";
      remove.textContent = "×";
      remove.title = "Stop watching";
      remove.setAttribute("aria-label", `Stop watching ${labelOf(k)}`);
      remove.addEventListener("click", () => unwatch(k - 1));
      head.append(remove);
    }
    row.append(head);
    const scale = k === focused ? document.createElement("div") : null;
    if (scale) row.append(scale, lookControls(k));
    list.append(row);
    rows.push({ k, value, scale });
  }
  return rows;
}

let deviceKey = null;

/** The inspected device, and a switch for every sensor of the program; rebuilt only when they change. */
function renderDevice() {
  const id = inspected();
  const names = sensorsOf(python.code ?? "");
  const neighbours = network.inRange[id].length;
  const key = `${id}|${neighbours}|${names.map((name) => `${name}:${world.sensors.get(name)?.has(id)}`).join(",")}`;
  if (key === deviceKey) return;
  deviceKey = key;
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
  worldChanged();
}

/** The network changed: Python hears of it at the next frame, once however many changes come. */
function worldChanged() {
  network = connect();
  element("pg-radius").value = network.range;
  element("pg-radius-value").textContent = network.range.toFixed(2);
  world.dirty = true;
  app.panelDirty = true;
  changed();
}

/**
 * Adds devices to the running network, or takes the last ones away; the others keep their
 * state. The radius follows the number, so that each device keeps hearing a few others.
 */
function setDeviceCount(count) {
  // A sensor on a device taken away moves to the nearest device left, as the source of the walkthrough does.
  for (const on of world.sensors.values()) {
    for (const id of [...on]) {
      if (id >= count) {
        on.delete(id);
        on.add(nearest(placesNow()[id], count));
      }
    }
  }
  world.count = count;
  // A device added back starts where the reader placed it, not where its program had moved it.
  world.moved = world.moved.slice(0, count);
  world.ranges = [];
  display.x.fill(NaN, count);
  display.y.fill(NaN, count);
  world.radius = null;
  element("pg-devices-value").textContent = count;
  if (app.hovered !== null && app.hovered >= count) app.hovered = null;
  if (app.selected >= count) app.selected = 0;
  worldChanged();
}

/** Moves device `id` to `point`, kept inside the arena; null when the pointer is off the plane. */
function move(id, point) {
  if (!point) return;
  const margin = app.moved ? WORLD_MARGIN : 0;
  const inside = (value) => Math.max(-margin, Math.min(SPAN + margin, value));
  world.places[id] = { x: inside(point.x), y: inside(point.y) };
  world.moved[id] = world.places[id];
  worldChanged();
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
  if (!python.worker && snapshot) state = "stopped";
  else if (snapshot?.paused) state = "stopped by an error";
  else if (python.program && snapshot?.stable) state = "stable";
  else if (python.program) state = app.playing ? "changing" : "paused";
  const live = app.playing && state === "changing";
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

/**
 * The view of the stack, for a link: how the result is drawn, the watches that edits left,
 * where they are in the editor with their names and looks, the front, and the modes.
 */
function viewOf() {
  return {
    look: app.look,
    watches: kept().map(({ mark, label, look }) => [mark.start, mark.end, label, look]),
    focus: app.focus,
    solo: app.solo,
    flat: app.flat,
    layout: app.layout,
  };
}

/** Opens `view` with the code it was taken from, which the editor holds. */
function openView(view) {
  Object.assign(app.look, view.look);
  watches = view.watches.map(([start, end, label, look]) => ({
    start,
    end,
    label,
    look: { ...defaultLook(), ...look },
    mark: { start, end },
  }));
  app.focus = view.focus;
  renderMarks();
  setSolo(Boolean(view.solo));
  setFlat(Boolean(view.flat));
  setLayout(view.layout);
}

async function share() {
  const url = new URL(window.location.href);
  url.hash = `code=${encode(editor.code)}&view=${encode(JSON.stringify(viewOf()))}`;
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
  menu.show(example.title);
  element("pg-summary").textContent = example.summary.replace(/^./, (first) => first.toUpperCase());
  const response = await fetch(new URL(`examples/${example.name}.py`, base));
  watches = [];
  editor.setCode(await response.text());
  run();
}

async function openFromHash() {
  const hash = new URLSearchParams(window.location.hash.slice(1));
  if (!hash.has("code")) {
    await openExample(hash.get("example"));
    return;
  }
  menu.show("Shared program");
  element("pg-summary").textContent = "A shared program.";
  watches = [];
  editor.setCode(decode(hash.get("code")));
  if (hash.has("view")) {
    try {
      openView(JSON.parse(decode(hash.get("view"))));
    } catch {
      // A link cut short, or edited by hand: the program alone is still worth opening.
      watches = [];
    }
  }
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

// A device dragged in 3D slides on the plane of the layer it was grabbed in, so that it stays under the pointer.
bindPointer(element("wt-scene"), {
  pick: scene.pick,
  grab: (id, x, y) => scene.pickInstance(x, y),
  drag: (grabbed, x, y) => move(grabbed.id, scene.groundAt(x, y, grabbed.z)),
  orbit: (dx, dy) => {
    if (app.flat) return;
    scene.orbit(dx, dy);
    changed();
  },
  hover,
  select,
});
bindPointer(element("wt-map"), {
  pick: map.pick,
  grab: (id) => ({ id }),
  drag: (grabbed, x, y) => move(grabbed.id, map.worldAt(x, y)),
  hover,
  select,
});

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
element("pg-watch").addEventListener("click", watch);
element("pg-solo").addEventListener("click", () => setSolo(!app.solo));
element("pg-stop").addEventListener("click", () => stop("Stopped. Python starts again at the next run."));
element("pg-share").addEventListener("click", share);
element("pg-layout").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) setLayout(button.dataset.show);
});
element("wt-play").addEventListener("click", () => setPlaying(!app.playing));
element("wt-round-step").addEventListener("click", stepOnce);
element("wt-restart").addEventListener("click", restart);
element("wt-home").addEventListener("click", () => {
  scene.reset();
  if (app.flat) Object.assign(scene.camera, ABOVE);
  changed();
});
element("pg-flat").addEventListener("click", () => setFlat(!app.flat));
element("pg-devices").addEventListener("input", (event) => setDeviceCount(Number(event.target.value)));
element("pg-radius").addEventListener("input", (event) => {
  world.radius = Number(event.target.value);
  // Every range starts over from the radius, in Python too.
  world.ranges = [];
  worldChanged();
});
element("pg-speed").addEventListener("change", (event) => {
  app.speed = Number(event.target.value);
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
  } else if (event.key === "s" || event.key === "S") {
    setSolo(!app.solo);
  } else if (["1", "2", "3"].includes(event.key)) {
    setLayout(LAYOUTS[Number(event.key) - 1]);
  } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
    // The arrows walk the stack; with Shift, they carry the layer in front along.
    event.preventDefault();
    const step = event.key === "ArrowUp" ? -1 : 1;
    if (event.shiftKey) moveWatch(focusedLayer(), step);
    else moveFocus(step);
  }
});

window.addEventListener("themechange", () => {
  app.palette = extendPalette(readPalette());
  refreshLooks();
  app.panelDirty = true;
  changed();
});

// Resizing clears the canvases after this frame was drawn: draw them again before the page is painted.
const resize = () => {
  scene.resize();
  map.resize();
  ease(0); // a layer that appeared since the last frame gets its heights
  draw(performance.now());
};
new ResizeObserver(resize).observe(element("wt-stage"));

let lastFrame = performance.now();

function frame(now) {
  const elapsed = Math.min(64, now - lastFrame);
  lastFrame = now;
  if (world.dirty && python.worker) {
    sendWorld();
    world.dirty = false;
  }
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
  menu.setExamples(examples);
  await openFromHash();
  // A link to another example or program, followed from this page, changes only the hash.
  window.addEventListener("hashchange", openFromHash);
}

Object.assign(element("pg-devices"), { min: FEWEST_DEVICES, max: MOST, value: world.count });
element("pg-devices-value").textContent = world.count;
worldChanged();
resize();
requestAnimationFrame(frame);
start().catch((error) => {
  status(`The playground could not load its examples: ${error.message}`);
});

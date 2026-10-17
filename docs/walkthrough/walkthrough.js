/*
 * The walkthrough page: a few steps, each running a program on the network.
 * The network is drawn in 3D and from above, next to the same field at
 * infinite density, and the program shows what the inspected device computed.
 */
import { RESOLUTION, createContinuum } from "./continuum.js";
import { createMap } from "./map.js";
import { FEWEST, MOST, SIZE, SPAN, createNetwork, fire, initialStates, isStable, seeded, shuffled } from "./model.js";
import { readPalette, toneIndex } from "./palette.js";
import { bindPointer } from "./pointer.js";
import { HIDDEN, LIFT, PULSE_MS, createScene } from "./scene.js";
import { STEPS } from "./steps.js";
import { VIEWS } from "./views.js";

const ROUND_MS = 700; // how long a round lasts while playing: every device runs once in it
const EASE_MS = 140; // how fast heights follow a change of value
const SETTLE_ROUNDS = 100; // a step that opens settled gives up after this many rounds
const calm = matchMedia("(prefers-reduced-motion: reduce)");
const element = (id) => document.getElementById(id);

let network = createNetwork();
const continuum = createContinuum();
const random = seeded(2026);
// The source and the target sit inside the arena, so that the channel between them is a whole ellipse;
// the target is the closer to the camera, which looks down into its gradient.
const environment = { source: SIZE * SIZE - SIZE - 2, target: SIZE + 1, off: new Set(), width: 0.8 };
const scene = createScene(element("wt-scene"));
const map = createMap(element("wt-map"));

const app = {
  step: 0,
  pinnedView: null, // a field chosen by clicking a line of the program
  round: 0,
  states: initialStates(network),
  stable: false,
  playing: true,
  showCloud: true,
  hovered: null,
  selected: 2 * SIZE + 2, // a device in the middle, on the way from the source to the target
  palette: readPalette(),
  environmentVersion: 0,
  computedVersion: -1,
  dirty: true, // the views need drawing again
  panelDirty: true, // the panel needs the values of the last runs
};

// The round in progress: the random order of the devices, the next to run, and the states it started from.
const rounds = { order: [], next: 0, start: null, owed: 0 };

const display = {
  deviceZ: new Float32Array(network.devices.length),
  ranAt: new Float64Array(network.devices.length),
  cloud: null,
  cloudKey: null,
};

/** Where the cloud points are drawn: the grid, shaken a little so that it reads as a cloud. */
const cloudPoints = (() => {
  const { grid } = continuum;
  const shake = (seed) => {
    const noise = Math.sin(seed * 12.9898) * 43758.5453;
    return noise - Math.floor(noise) - 0.5;
  };
  const spacing = SPAN / (RESOLUTION - 1);
  const clamp = (value) => Math.max(0, Math.min(SPAN, value));
  return {
    x: Float32Array.from(grid.x, (x, index) => clamp(x + 0.7 * spacing * shake(index))),
    y: Float32Array.from(grid.y, (y, index) => clamp(y + 0.7 * spacing * shake(index + 7919))),
  };
})();

const step = () => STEPS[app.step];
const viewName = () => app.pinnedView ?? step().view;
const view = () => VIEWS[viewName()];
const inspected = () => app.hovered ?? app.selected;
const isOn = (id) => !environment.off.has(id);
const roleOf = (id) => step().roles.find((role) => environment[role] === id) ?? null;

function linkLength(a, b) {
  return network.inRange[a].find((neighbor) => neighbor.id === b)?.length ?? NaN;
}

function changed() {
  app.dirty = true;
}

// --- Rounds: every device runs once per round, in random order ----------------------------

function beginRound() {
  rounds.order = shuffled(network.devices.length, random);
  rounds.next = 0;
  rounds.start = app.states;
}

/** Runs the next device of the round; at the end of the round, checks whether anything changed. */
function runNext(now) {
  const id = rounds.order[rounds.next];
  rounds.next += 1;
  if (isOn(id)) {
    app.states = app.states.with(id, fire(network, environment, app.states, id));
    display.ranAt[id] = now;
  }
  if (rounds.next === rounds.order.length) {
    app.round += 1;
    app.stable = isStable(rounds.start, app.states, step().fields);
    beginRound();
  }
  app.panelDirty = true;
  changed();
}

function finishRound(now) {
  const round = app.round;
  while (app.round === round) runNext(now);
}

/** Runs rounds until the program of the step reaches its fixpoint, or gives up. */
function settle() {
  while (!app.stable && app.round < SETTLE_ROUNDS) finishRound(-Infinity);
}

function restart() {
  app.states = initialStates(network);
  app.round = 0;
  app.stable = false;
  rounds.owed = 0;
  beginRound();
  app.panelDirty = true;
  changed();
}

function setPlaying(playing) {
  app.playing = playing;
  app.panelDirty = true;
}

function refreshPlayer() {
  const play = element("wt-play");
  play.classList.toggle("is-paused", !app.playing);
  play.title = app.playing ? "Pause (Space)" : "Play (Space)";
  play.setAttribute("aria-label", app.playing ? "Pause" : "Play");
  let status = "changing";
  if (app.round === 0 && rounds.next === 0) status = "not started";
  else if (app.stable) status = "stable";
  element("wt-round").innerHTML =
    `<span class="wt-status${app.stable || status === "not started" ? " is-stable" : ""}"></span>` +
    `round <strong>${app.round}</strong> · ${status}`;
}

// --- The environment ----------------------------------------------------------------------

function environmentChanged() {
  app.environmentVersion += 1;
  app.stable = false;
  app.panelDirty = true;
  changed();
}

function nearestOn(point, except) {
  let best = null;
  let bestDistance = Infinity;
  for (const device of network.devices) {
    const distance = Math.hypot(device.x - point.x, device.y - point.y);
    if (isOn(device.id) && !except.includes(device.id) && distance < bestDistance) {
      best = device.id;
      bestDistance = distance;
    }
  }
  return best;
}

function setRole(role, id) {
  const other = role === "source" ? "target" : "source";
  if (environment[role] === id) return;
  if (environment[other] === id) environment[other] = environment[role];
  environment.off.delete(id);
  environment[role] = id;
  environmentChanged();
}

function toggleOff(id) {
  if (environment.off.has(id)) {
    environment.off.delete(id);
  } else {
    // The source and the target stay on a device that runs: they move to the closest one.
    const role = ["source", "target"].find((each) => environment[each] === id);
    const other = role === "source" ? environment.target : environment.source;
    const refuge = role ? nearestOn(network.devices[id], [id, other]) : null;
    if (role && refuge === null) return;
    environment.off.add(id);
    if (role) environment[role] = refuge;
    // A device that is switched off stops sharing at once: its neighbors no longer hear it.
    app.states = app.states.with(id, null);
  }
  environmentChanged();
}

/** Adds devices to the running network, or takes the last ones away; the others keep their state. */
function setDeviceCount(count) {
  const before = network;
  network = createNetwork(count);
  const resized = (values, Kind) => {
    const next = new Kind(count);
    next.set(values.subarray(0, Math.min(count, values.length)));
    return next;
  };
  app.states = Array.from({ length: count }, (_, id) => app.states[id] ?? null);
  display.deviceZ = resized(display.deviceZ, Float32Array);
  display.ranAt = resized(display.ranAt, Float64Array);
  for (const id of environment.off) {
    if (id >= count) environment.off.delete(id);
  }
  for (const role of ["source", "target"]) {
    const other = role === "source" ? environment.target : environment.source;
    if (environment[role] >= count) environment[role] = nearestOn(before.devices[environment[role]], [other]);
  }
  if (app.selected >= count) app.selected = 2 * SIZE + 2;
  if (app.hovered !== null && app.hovered >= count) app.hovered = null;
  // The round in progress started without the new devices: a new one starts with them.
  beginRound();
  renderLegend();
  environmentChanged();
}

// --- What the views draw ------------------------------------------------------------------

function refreshCloud() {
  if (app.computedVersion !== app.environmentVersion) {
    continuum.update(environment, network);
    app.computedVersion = app.environmentVersion;
  }
  const name = viewName();
  const key = `${name}|${app.palette.dark}|${app.computedVersion}`;
  if (display.cloudKey === key) return;
  const shown = VIEWS[name];
  const reversed = Boolean(shown.scale?.reversed);
  const { height, tone, curve, water } = shown.cloud(continuum.fields, environment);
  const target = Float32Array.from(height, (value) => value * LIFT);
  const z = display.cloud ? display.cloud.z : Float32Array.from(target);
  target.forEach((value, index) => {
    if (!Number.isFinite(z[index])) z[index] = value;
  });
  display.cloud = {
    ...cloudPoints,
    z,
    target,
    color: Uint8Array.from(tone, (value) => toneIndex(value, reversed) ?? HIDDEN),
    curve: curve?.map((point) => ({ x: point.x, y: point.y, z: point.height * LIFT })),
    curveColor: shown.boolean ? app.palette.on : toneIndex(0, reversed),
    water,
  };
  display.cloudKey = key;
  changed();
}

function devicesFor(shown) {
  const reversed = Boolean(shown.scale?.reversed);
  return network.devices.map((device) => {
    const state = app.states[device.id];
    const off = !isOn(device.id);
    const looks = state && !off ? shown.device(state, network) : { height: null, tone: null };
    return {
      id: device.id,
      x: device.x,
      y: device.y,
      z: display.deviceZ[device.id],
      lift: (looks.height ?? 0) * LIFT,
      color: toneIndex(looks.tone, reversed),
      off,
      role: roleOf(device.id),
      ranAt: display.ranAt[device.id],
    };
  });
}

function linksFor(shown) {
  const { states } = app;
  if (shown.links === "none") return [];
  return network.links
    .filter((link) => isOn(link.a) && isOn(link.b))
    .map((link) => {
      const a = states[link.a];
      const b = states[link.b];
      if (shown.links !== "branches" || a === null || b === null) return { a: link.a, b: link.b, style: shown.links };
      if (a.branch !== b.branch) return { a: link.a, b: link.b, style: "cut" };
      return { a: link.a, b: link.b, style: a.branch };
    });
}

function focusFor(shown) {
  const id = app.hovered;
  if (id === null) return { focus: null, highlights: [] };
  const state = isOn(id) ? app.states[id] : null;
  const talks = state !== null && shown.links !== "none";
  const neighbors = talks ? (shown.links === "branches" ? state.sameBranch : state.heard) : [];
  const via = state && shown.via ? shown.via(state) : null;
  let text = "has not run yet";
  if (!isOn(id)) text = "switched off";
  else if (state) text = shown.text(state);
  return {
    focus: { id, neighbors, range: Boolean(shown.range) && isOn(id), label: `#${id} · ${text}` },
    highlights: neighbors.map((neighbor) => ({ a: id, b: neighbor, style: neighbor === via ? "via" : "neighbor" })),
  };
}

/** Moves the heights a step toward their values; true while anything still moves. */
function ease(devices, elapsed) {
  const pull = calm.matches ? 1 : 1 - Math.exp(-elapsed / EASE_MS);
  let moving = false;
  for (const device of devices) {
    const gap = device.lift - display.deviceZ[device.id];
    if (Math.abs(gap) > 1e-3) moving = true;
    display.deviceZ[device.id] += gap * pull;
    device.z = display.deviceZ[device.id];
  }
  const { z, target } = display.cloud;
  for (let index = 0; index < z.length; index += 1) {
    const gap = target[index] - z[index];
    if (Math.abs(gap) > 1e-3) {
      moving = true;
      z[index] += gap * pull;
    }
  }
  return moving;
}

let lastFrame = performance.now();

function frame(now) {
  const elapsed = Math.min(64, now - lastFrame);
  lastFrame = now;
  if (app.playing) {
    rounds.owed += (elapsed / ROUND_MS) * network.devices.length;
    for (; rounds.owed >= 1; rounds.owed -= 1) runNext(now);
  }
  if (app.panelDirty) {
    refreshInspection();
    refreshPlayer();
    app.panelDirty = false;
  }
  refreshCloud();
  const shown = view();
  const devices = devicesFor(shown);
  const pulsing = devices.some((device) => now - device.ranAt < PULSE_MS);
  if (ease(devices, elapsed) || app.dirty || pulsing) {
    const { focus, highlights } = focusFor(shown);
    const drawing = {
      palette: app.palette,
      network,
      devices,
      links: linksFor(shown),
      highlights,
      focus,
      selected: app.selected,
      cloud: app.showCloud ? display.cloud : null,
      camera: scene.camera,
      density: Math.sqrt(FEWEST / network.devices.length),
      now,
      pulses: !calm.matches,
    };
    scene.draw(drawing);
    map.draw(drawing);
    app.dirty = false;
  }
  requestAnimationFrame(frame);
}

// --- The panel ----------------------------------------------------------------------------

let codeLines = [];

function renderSteps() {
  const nav = element("wt-steps");
  nav.replaceChildren(
    ...STEPS.map((each, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wt-step";
      button.innerHTML = `<span class="wt-step-number">${index + 1}</span><span class="wt-step-name">${each.name}</span>`;
      button.addEventListener("click", () => goTo(index));
      return button;
    }),
  );
}

function renderStory() {
  const current = step();
  element("wt-kicker").textContent = `Step ${app.step + 1} of ${STEPS.length}`;
  element("wt-title").textContent = current.title;
  element("wt-text").innerHTML = current.text.map((paragraph) => `<p>${paragraph}</p>`).join("");
  element("wt-try").textContent = current.hint;
  element("wt-width-row").hidden = !current.width;
  const playground = element("wt-playground");
  playground.hidden = !current.playground;
  playground.href = `../playground/#example=${current.playground ?? ""}`;
  element("wt-previous").disabled = app.step === 0;
  element("wt-next").disabled = app.step === STEPS.length - 1;
  element("wt-steps").querySelectorAll(".wt-step").forEach((button, index) => {
    if (index === app.step) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-action=source], [data-action=target]").forEach((button) => {
    button.hidden = !current.roles.includes(button.dataset.action);
  });
}

function showView(name) {
  app.pinnedView = name === viewName() || name === step().view ? null : name;
  refreshInspection();
  renderLegend();
  changed();
}

function renderCode() {
  const container = element("wt-code");
  codeLines = step().code.map((line) => {
    const row = document.createElement("div");
    row.className = "wt-line";
    const source = document.createElement("div");
    source.className = "wt-src";
    source.innerHTML = globalThis.highlightPython(line.code);
    const output = document.createElement("div");
    output.className = "wt-out";
    const indent = document.createElement("span");
    indent.className = "wt-indent";
    indent.textContent = line.code.match(/^ */)[0];
    const value = document.createElement("span");
    value.className = "wt-value";
    const detail = document.createElement("span");
    output.append(indent, "↳", value, detail);
    row.append(source, output);
    if (line.view) {
      row.dataset.view = line.view;
      row.tabIndex = 0;
      row.setAttribute("role", "button");
      row.title = "Show this field";
      row.addEventListener("click", () => showView(line.view));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          showView(line.view);
        }
      });
    }
    return { line, row, output, value, detail };
  });
  container.replaceChildren(...codeLines.map(({ row }) => row));
}

/** The values of the inspected device, line by line, and its name and actions. */
function refreshInspection() {
  const id = inspected();
  const state = isOn(id) ? app.states[id] : null;
  const context = state ? { id, state, environment, round: app.round, length: (other) => linkLength(id, other) } : null;
  const shown = viewName();
  for (const { line, row, output, value, detail } of codeLines) {
    const skipped = Boolean(state && line.branch && line.branch !== state.branch);
    const known = Boolean(context || line.parameter);
    row.classList.toggle("is-skipped", skipped);
    row.classList.toggle("is-shown", line.view === shown && !skipped);
    if (line.view) row.setAttribute("aria-pressed", String(line.view === shown));
    value.textContent = line.value && known && !skipped ? line.value(context ?? { environment }) : "";
    detail.textContent = (line.detail && context && !skipped && line.detail(context)) || "";
    output.hidden = !value.textContent && !detail.textContent;
  }
  let status = "has not run yet";
  if (!isOn(id)) status = "switched off";
  else if (state && view().links === "none") status = "runs alone";
  else if (state) status = `hears ${state.heard.length} neighbor${state.heard.length === 1 ? "" : "s"}`;
  element("wt-device-name").innerHTML = `<strong>#${id}</strong> · ${status}`;
  for (const button of document.querySelectorAll("[data-action]")) {
    const action = button.dataset.action;
    if (action === "off") {
      button.textContent = isOn(id) ? "switch off" : "switch on";
    } else {
      button.disabled = environment[action] === id;
    }
  }
}

function renderLegend() {
  const shown = view();
  const { palette } = app;
  const reversed = Boolean(shown.scale?.reversed);
  const swatch = (color, label) =>
    `<span class="wt-key"><span class="wt-key-swatch" style="background:${color}"></span>${label}</span>`;
  let scale = "";
  if (shown.boolean) {
    scale = `<div class="wt-legend-keys">${swatch(palette.css[palette.on], "True")}${swatch(palette.css[palette.off], "False")}</div>`;
  } else {
    const stops = Array.from({ length: 9 }, (_, k) => palette.css[toneIndex(k / 8, reversed)]).join(", ");
    const end = typeof shown.scale.to === "function" ? shown.scale.to(network) : shown.scale.to;
    scale =
      `<div class="wt-legend-bar" style="background:linear-gradient(90deg, ${stops})"></div>` +
      `<div class="wt-legend-ends"><span>${shown.scale.from}</span><span>${end}</span></div>`;
  }
  const keys = [
    `<span class="wt-key"><span class="wt-key-swatch" style="background:currentColor"></span>devices</span>`,
    app.showCloud ? `<span class="wt-key"><span class="wt-key-cloud"></span>infinite density</span>` : "",
  ];
  element("wt-legend").innerHTML =
    `<div class="wt-legend-label">${shown.label}</div>${scale}<div class="wt-legend-keys">${keys.join("")}</div>`;
}

function goTo(index) {
  app.step = Math.max(0, Math.min(STEPS.length - 1, index));
  app.pinnedView = null;
  history.replaceState(null, "", `#step=${app.step + 1}`);
  renderStory();
  renderCode();
  renderLegend();
  // Every step deploys a new program: the devices start over from their first round. A
  // composition opens settled, as its first rounds mostly show infinities meeting.
  restart();
  if (step().warm) settle();
}

// --- Pointer, keyboard and controls --------------------------------------------------------

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

function moveRole(role, point) {
  const other = role === "source" ? environment.target : environment.source;
  const id = nearestOn(point, [other]);
  if (id !== null && id !== environment[role]) setRole(role, id);
}

/** Dragging the source or the target moves it to the device nearest the point under the pointer. */
const dragRole = (toWorld) => (role, x, y) => {
  const point = toWorld(x, y);
  if (point) moveRole(role, point);
};

bindPointer(element("wt-scene"), {
  pick: scene.pick,
  grab: roleOf,
  drag: dragRole(scene.groundAt),
  orbit: (dx, dy) => {
    scene.orbit(dx, dy);
    changed();
  },
  hover,
  select,
});
bindPointer(element("wt-map"), { pick: map.pick, grab: roleOf, drag: dragRole(map.worldAt), hover, select });

element("wt-scene").addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    scene.zoom(Math.exp(-event.deltaY * 0.0015));
    changed();
  },
  { passive: false },
);

element("wt-previous").addEventListener("click", () => goTo(app.step - 1));
element("wt-next").addEventListener("click", () => goTo(app.step + 1));
element("wt-play").addEventListener("click", () => setPlaying(!app.playing));
element("wt-round-step").addEventListener("click", () => {
  setPlaying(false);
  finishRound(performance.now());
});
element("wt-restart").addEventListener("click", restart);
element("wt-home").addEventListener("click", () => {
  scene.reset();
  changed();
});
element("wt-cloud").addEventListener("click", (event) => {
  app.showCloud = !app.showCloud;
  event.currentTarget.setAttribute("aria-pressed", String(app.showCloud));
  renderLegend();
  changed();
});
element("wt-width").addEventListener("input", (event) => {
  environment.width = Number(event.target.value);
  element("wt-width-value").textContent = environment.width.toFixed(1);
  environmentChanged();
});
element("wt-devices").addEventListener("input", (event) => {
  element("wt-devices-value").textContent = event.target.value;
  setDeviceCount(Number(event.target.value));
});
for (const button of document.querySelectorAll("[data-action]")) {
  button.addEventListener("click", () => {
    const id = inspected();
    if (button.dataset.action === "off") toggleOff(id);
    else setRole(button.dataset.action, id);
  });
}

document.addEventListener("keydown", (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey || event.target.closest("input, select, textarea")) return;
  const onControl = event.target.closest("button, [role=button], a");
  if (event.key === "ArrowRight") goTo(app.step + 1);
  else if (event.key === "ArrowLeft") goTo(app.step - 1);
  else if (event.key === " " && !onControl) {
    event.preventDefault();
    setPlaying(!app.playing);
  } else if (event.key === ".") {
    setPlaying(false);
    finishRound(performance.now());
  } else if (event.key === "r" || event.key === "R") restart();
});

window.addEventListener("themechange", () => {
  app.palette = readPalette();
  display.cloudKey = null;
  renderLegend();
  changed();
});

const resize = () => {
  scene.resize();
  map.resize();
  changed();
};
new ResizeObserver(resize).observe(element("wt-stage"));

Object.assign(element("wt-devices"), { min: FEWEST, max: MOST, value: FEWEST });
element("wt-devices-value").textContent = FEWEST;
renderSteps();
const linked = Number(new URLSearchParams(window.location.hash.slice(1)).get("step"));
goTo(Number.isInteger(linked) && linked > 0 ? linked - 1 : 0);
resize();
requestAnimationFrame(frame);

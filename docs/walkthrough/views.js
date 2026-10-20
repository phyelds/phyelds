/*
 * How each field of the programs is drawn: the height and the tone of every
 * device, and the same field at infinite density for the cloud.
 *
 * Heights and tones are in [0, 1]. A tone of ON or OFF marks a boolean; a null
 * height or tone (NaN on the grid) marks a device or a point without a value.
 */
import { region } from "./continuum.js";
import { CAP, HOT, SPAN, TEMPERATURE } from "./model.js";

export const ON = 2;
export const OFF = 3;
const LONGEST = Math.hypot(SPAN, SPAN); // the longest distance in the arena
const PLATEAU = 0.5; // the height of True in a channel

const distanceHeight = (distance) => (Number.isFinite(distance) ? distance / LONGEST : null);
const warmth = (degrees) => (degrees - TEMPERATURE.min) / (TEMPERATURE.max - TEMPERATURE.min);
// The temperature capped at HOT: whatever is above it is just True, so it sits flat on the cut.
const capped = (degrees) => warmth(Math.min(degrees, HOT));

function gridOf(values, toHeight, toTone = toHeight) {
  const height = new Float32Array(values.length);
  const tone = new Float32Array(values.length);
  values.forEach((value, index) => {
    const known = Number.isFinite(value);
    height[index] = (known ? toHeight(value) : null) ?? NaN;
    tone[index] = (known ? toTone(value) : null) ?? NaN;
  });
  return { height, tone };
}

/** Points along the shortest curve, each at `heightAt(distance travelled, length)`. */
function curveOf(path, heightAt) {
  const points = [];
  let travelled = 0;
  const length = path.slice(1).reduce((total, point, k) => total + Math.hypot(point.x - path[k].x, point.y - path[k].y), 0);
  for (let k = 1; k < path.length; k += 1) {
    const a = path[k - 1];
    const b = path[k];
    const segment = Math.hypot(b.x - a.x, b.y - a.y);
    const steps = Math.max(1, Math.ceil(segment / 0.03));
    for (let s = 0; s < steps; s += 1) {
      const t = s / steps;
      points.push({ x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y), height: heightAt(travelled + t * segment, length) });
    }
    travelled += segment;
  }
  const last = path[path.length - 1];
  points.push({ x: last.x, y: last.y, height: heightAt(length, length) });
  return points;
}

const scalar = (height) => ({ height, tone: height });
const number = (value) => (Number.isFinite(value) ? value.toFixed(2) : "inf");

export const VIEWS = {
  temperature: {
    label: "temperature",
    scale: { from: `${TEMPERATURE.min} °C`, to: `${TEMPERATURE.max} °C` },
    links: "none",
    text: (state) => `${state.temperature.toFixed(1)} °C`,
    device: (state) => scalar(warmth(state.temperature)),
    cloud: (fields) => gridOf(fields.temperature, warmth),
  },
  hot: {
    label: `temperature > ${HOT}`,
    boolean: true,
    links: "none",
    text: (state) => (state.temperature > HOT ? "hot" : "not hot"),
    device: (state) => ({ height: capped(state.temperature), tone: state.temperature > HOT ? ON : OFF }),
    // The plane at HOT cuts the temperature: what rose above it is True, flat on the cut.
    cloud: (fields) => ({
      ...gridOf(fields.temperature, capped, (degrees) => (degrees > HOT ? ON : OFF)),
      water: { ...region(fields.grid, fields.temperature.map((degrees) => -degrees), -HOT), height: warmth(HOT), label: `${HOT} °C` },
    }),
  },
  neighbors: {
    label: "neighbors in range",
    // Counted against a device far from the border, whose whole range is inside the arena.
    scale: { from: "0", to: (network) => String(network.typical) },
    links: "plain",
    range: true,
    text: (state) => `${state.heard.length} in range`,
    device: (state, network) => scalar(state.heard.length / network.typical),
    cloud: (fields) => gridOf(fields.share, (share) => share),
  },
  rounds: {
    label: "rounds counted",
    scale: { from: "0", to: String(CAP) },
    links: "none",
    text: (state) => `${state.rounds} rounds`,
    device: (state) => scalar(state.rounds / CAP),
    // Every point keeps counting until the cap: the fixpoint is flat.
    cloud: (fields) => gridOf(fields.temperature, () => 1),
  },
  toTarget: {
    label: "distance to the target",
    scale: { from: "0", to: LONGEST.toFixed(1), reversed: true },
    links: "plain",
    via: (state) => state.toTarget.via,
    text: (state) => number(state.toTarget.distance),
    device: (state) => scalar(distanceHeight(state.toTarget.distance)),
    cloud: (fields) => gridOf(fields.toTarget, distanceHeight),
  },
  toSource: {
    label: "distance to the source",
    scale: { from: "0", to: LONGEST.toFixed(1), reversed: true },
    links: "plain",
    via: (state) => state.toSource.via,
    text: (state) => number(state.toSource.distance),
    device: (state) => scalar(distanceHeight(state.toSource.distance)),
    cloud: (fields) => gridOf(fields.toSource, distanceHeight),
  },
  between: {
    label: "distance between source and target",
    scale: { from: "0", to: LONGEST.toFixed(1), reversed: true },
    links: "plain",
    via: (state) => state.between.via,
    text: (state) => number(state.between.value),
    device: (state) => scalar(distanceHeight(state.between.value)),
    cloud: (fields) => ({
      ...gridOf(fields.toTarget, () => distanceHeight(fields.between)),
      curve: curveOf(fields.path, () => distanceHeight(fields.between)),
    }),
  },
  channel: {
    label: "to_source + to_target <= between + width",
    boolean: true,
    links: "faint",
    text: (state) => (state.inChannel ? "in the channel" : "outside"),
    // True is a plateau in the middle, False stays on the ground.
    device: (state) => ({ height: state.inChannel ? PLATEAU : 0, tone: state.inChannel ? ON : OFF }),
    cloud: (fields, environment) => {
      const level = fields.between + environment.width;
      return {
        ...gridOf(fields.sum, (sum) => (sum <= level ? PLATEAU : 0), (sum) => (sum <= level ? ON : OFF)),
        curve: curveOf(fields.path, () => PLATEAU),
        water: { ...region(fields.grid, fields.sum, level), height: PLATEAU, label: "between + width" },
      };
    },
  },
  split: {
    label: "distance to the source",
    scale: { from: "0", to: LONGEST.toFixed(1), reversed: true },
    links: "branches",
    via: (state) => state.split.via,
    text: (state) => number(state.split.distance),
    device: (state) => scalar(distanceHeight(state.split.distance)),
    cloud: (fields) => gridOf(fields.split, distanceHeight),
  },
};

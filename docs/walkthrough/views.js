/*
 * How each field of the programs is drawn: the height and the tone of every
 * device, and the same field at infinite density for the cloud.
 *
 * Heights and tones are in [0, 1]. A tone of ON or OFF marks a boolean; a null
 * height or tone (NaN on the grid) marks a device or a point without a value.
 */
import { region } from "./continuum.js";
import { SPAN, TEMPERATURE } from "./model.js";

export const ON = 2;
export const OFF = 3;
const LONGEST = Math.hypot(SPAN, SPAN); // the longest distance in the arena

const distanceHeight = (distance) => (Number.isFinite(distance) ? distance / LONGEST : null);
const warmth = (degrees) => (degrees - TEMPERATURE.min) / (TEMPERATURE.max - TEMPERATURE.min);

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
    device: (state) => ({
      height: distanceHeight(state.toSource.distance + state.toTarget.distance),
      tone: state.inChannel ? ON : OFF,
    }),
    // The sum is a valley along the shortest path; flooded up to between + width, the water is the channel.
    cloud: (fields, environment) => {
      const level = fields.between + environment.width;
      return {
        ...gridOf(fields.sum, distanceHeight, (sum) => (sum <= level ? ON : OFF)),
        curve: curveOf(fields.path, () => distanceHeight(fields.between)),
        water: { ...region(fields.grid, fields.sum, level), height: distanceHeight(level), label: "between + width" },
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

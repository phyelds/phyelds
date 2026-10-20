/*
 * The steps of the walkthrough: what each one says, the program it runs, and
 * what every line of the program evaluates to on the inspected device.
 *
 * A line can name a view (views.js): clicking it shows that field. Its `value`
 * and `detail` receive the inspected device (its id, and its state after the last
 * round), the environment, the round number, and the length of its link to a neighbor;
 * the value of a `parameter` line only needs the environment. A step is stable
 * when a round changes none of its `fields`, the parts of the state its program
 * computes; a `warm` step opens with its program already stable.
 */

import { CAP, HOT } from "./model.js";

const number = (value) => (Number.isFinite(value) ? value.toFixed(2) : "inf");
const python = (flag) => (flag ? "True" : "False");

/** Explains a distance_to estimate: the neighbor it came through, plus the link to it. */
function viaDetail(estimate, length, start, noValue) {
  if (estimate.via === null) {
    return Number.isFinite(estimate.distance) ? start : noValue;
  }
  const hop = length(estimate.via);
  return `via #${estimate.via}: ${number(estimate.distance - hop)} + ${number(hop)}`;
}

/** A line computing a gradient: its value, and the field it shows when clicked. */
const gradientLine = (name, estimateOf) => ({
  value: ({ state }) => number(estimateOf(state).distance),
  view: name,
});

/** How a gradient line got its value, for the lines where that is the point. */
const explained = (estimateOf, start, noValue) => ({
  detail: ({ state, length }) => viaDetail(estimateOf(state), length, start, noValue),
});

function betweenDetail(between) {
  if (between.distance === 0) return "the source's own to_target";
  if (between.via === null) return "no news from the source yet: its own to_target";
  return `the source's to_target, via #${between.via}`;
}

export const STEPS = [
  {
    name: "Field",
    title: "A field, sampled by the devices",
    fields: ["temperature"],
    text: [
      "Think of a <strong>field</strong> as something continuous: a value at every point of space, like the temperature of a room. The cloud is that field, as if there were a device at every point.",
      "The devices <strong>sample</strong> it: each one runs the same program where it stands and gets its own value. Here, every device reads its <code>temperature</code> sensor, and a sensor needs no neighbors, so the samples sit right on the cloud.",
    ],
    hint: "Hover a device: the program shows what it computed.",
    view: "temperature",
    roles: [],
    code: [
      { code: "@aggregate" },
      { code: "def reading() -> float:" },
      { code: '    return sense("temperature")', view: "temperature", value: ({ state }) => state.temperature.toFixed(1) },
    ],
  },
  {
    name: "Operators",
    title: "Operators: fields in, fields out",
    fields: ["temperature"],
    text: [
      `A field is a value like any other: an operator applied to a field gives a new field, point by point. <code>temperature &gt; ${HOT}</code> compares the reading of every device with ${HOT}, and the result is a field of booleans: where it is hot.`,
      `In the cloud, the plane at ${HOT} °C cuts the temperature: what rose above it is <code>True</code>, and lies flat on the cut.`,
    ],
    hint: "Click a line of the program to see the field it computes.",
    view: "hot",
    roles: [],
    code: [
      { code: "@aggregate" },
      { code: "def hot() -> bool:" },
      { code: '    temperature = sense("temperature")', view: "temperature", value: ({ state }) => state.temperature.toFixed(1) },
      { code: `    return temperature > ${HOT}`, view: "hot", value: ({ state }) => python(state.temperature > HOT) },
    ],
  },
  {
    name: "Neighbors",
    title: "Neighbors: what a device sees",
    fields: ["heard"],
    text: [
      "<code>neighbors</code> is the <strong>spatial</strong> side of a program: it builds fields that take the neighborhood into account. <code>neighbors(1)</code> shares a value with the devices in range and returns what they shared, a <code>NeighborhoodField</code>. Its size is how many neighbors a device has: fewer along the border.",
      "At infinite density, everybody would hear infinitely many. The cloud shows what stays finite: the share of the range inside the space.",
    ],
    hint: "Hover a device to see its range, or switch it off from the panel.",
    view: "neighbors",
    roles: [],
    playground: "neighbours",
    code: [
      { code: "@aggregate" },
      { code: "def neighbor_count() -> int:" },
      {
        code: "    return len(neighbors(1).exclude_self())",
        view: "neighbors",
        value: ({ state }) => String(state.heard.length),
        detail: ({ state, round }) => (state.heard.length === 0 && round <= 1 ? "nothing received yet: first round" : null),
      },
    ],
  },
  {
    name: "Time",
    title: "Time: from round to round",
    fields: ["rounds"],
    text: [
      "<code>remember</code> is the <strong>temporal</strong> side: a device keeps a value from one round to the next. Here, each device counts its own rounds, so the field changes in time.",
      `Capped at ${CAP}, the count stops growing: the field reaches a <strong>fixpoint</strong>, the flat cloud, and stays there. A device switched off forgets what it kept: switched on again, it starts over from 0.`,
    ],
    hint: "Restart to watch the field rise and stop at the cap. Switch a device off and on again.",
    view: "rounds",
    roles: [],
    code: [
      { code: "@aggregate" },
      { code: "def rounds() -> int:" },
      { code: "    set_count, count = remember(0)" },
      { code: `    set_count(min(count + 1, ${CAP}))` },
      {
        code: "    return count",
        view: "rounds",
        value: ({ state }) => String(state.rounds),
        detail: ({ state }) => (state.rounds === CAP ? `min(${CAP} + 1, ${CAP}): capped` : null),
      },
    ],
  },
  {
    name: "Gradient",
    title: "Gradient: hop by hop",
    fields: ["toTarget"],
    text: [
      "The gradient puts space and time together. Each round, a device remembers its estimate (<code>remember</code>, time), shares it (<code>neighbors</code>, space), and takes the smallest neighbor estimate plus the distance to that neighbor. Round after round, the field spreads from the target, and settles just above the cloud: the network measures along its links, the cloud is the exact distance.",
      "It is <strong>self-stabilizing</strong>: from any state, it reaches the same field in a finite number of rounds, and stays there while nothing changes. So it is also <strong>self-healing</strong>: after any change, such as a moved target or a broken device, it repairs itself, with nobody in charge.",
    ],
    hint: "Restart to watch it spread. Drag the target, or switch devices off: the field repairs itself.",
    view: "toTarget",
    roles: ["target"],
    playground: "self_healing",
    code: [
      { code: "@aggregate" },
      { code: "def to_target() -> float:" },
      { code: "    distances = neighbors_distances()" },
      {
        code: '    return distance_to(sense("target"), distances)',
        ...gradientLine("toTarget", (state) => state.toTarget),
        ...explained((state) => state.toTarget, "the target itself", "no estimate has arrived yet"),
      },
    ],
  },
  {
    name: "Channel",
    title: "Compose: a channel",
    fields: ["toSource", "toTarget", "between"],
    text: [
      "Fields add and compare point by point. The gradients from the source and from the target add up to <code>between</code>, the length of the shortest path, along that path, and to more away from it.",
      "Where the sum stays within <code>between + width</code>, the comparison is <code>True</code>: the channel, a plateau in the middle, while the devices outside stay on the ground. At infinite density, it is an ellipse with foci in the source and the target.",
      "Combining self-stabilizing fields gives a self-stabilizing field: the gradients settle, and the channel built on them settles too. Move the source or the target, and it heals by itself.",
    ],
    hint: "Change the width, or drag the source and the target. Restart to watch it settle: while the distances are still infinite, inf <= inf holds.",
    view: "channel",
    warm: true,
    roles: ["source", "target"],
    width: true,
    playground: "channel",
    code: [
      { code: "@aggregate" },
      {
        code: "def channel(width: float) -> bool:",
        parameter: true,
        value: ({ environment }) => `width = ${environment.width.toFixed(1)}`,
      },
      {
        code: '    source, target = sense("source"), sense("target")',
        value: ({ id, environment }) => `${python(environment.source === id)}, ${python(environment.target === id)}`,
      },
      { code: "    distances = neighbors_distances()" },
      { code: "    to_source = distance_to(source, distances)", ...gradientLine("toSource", (state) => state.toSource) },
      { code: "    to_target = distance_to(target, distances)", ...gradientLine("toTarget", (state) => state.toTarget) },
      {
        code: "    between = distance_between(source, target, distances)",
        view: "between",
        value: ({ state }) => number(state.between.value),
        detail: ({ state }) => betweenDetail(state.between),
      },
      {
        code: "    return to_source + to_target <= between + width",
        view: "channel",
        value: ({ state }) => python(state.inChannel),
        detail: ({ state, environment }) =>
          `${number(state.toSource.distance)} + ${number(state.toTarget.distance)} <= ` +
          `${number(state.between.value)} + ${environment.width.toFixed(1)}`,
      },
    ],
  },
  {
    name: "Branch",
    title: "Branch: separate networks",
    fields: ["toSource", "toTarget", "between", "branch", "split"],
    text: [
      "An <code>if</code> splits the network: its branches are aligned apart, so devices in the channel only hear devices in the channel, and the others only the others. Links across the border carry nothing.",
      "Both branches run the same line, yet outside, the source is out of reach: the distance stays infinite.",
    ],
    hint: "Hover a device: the program shows the branch it takes.",
    view: "split",
    warm: true,
    roles: ["source", "target"],
    width: true,
    code: [
      { code: "@aggregate" },
      {
        code: "def split(width: float) -> float:",
        parameter: true,
        value: ({ environment }) => `width = ${environment.width.toFixed(1)}`,
      },
      { code: "    distances = neighbors_distances()" },
      { code: "    if channel(width):", view: "channel", value: ({ state }) => python(state.inChannel) },
      {
        code: '        return distance_to(sense("source"), distances)',
        branch: "inside",
        ...gradientLine("split", (state) => state.split),
        ...explained((state) => state.split, "the source itself", "no estimate has arrived yet"),
      },
      { code: "    else:", branch: "outside" },
      {
        code: '        return distance_to(sense("source"), distances)',
        branch: "outside",
        ...gradientLine("split", (state) => state.split),
        ...explained((state) => state.split, "the source itself", "the source is in the other branch"),
      },
    ],
  },
];

/*
 * The devices of the walkthrough and the aggregate programs they run.
 *
 * Devices run asynchronously, as in the simulator of phyelds: in every round,
 * each device runs once, in random order, and reads what its neighbors last
 * shared, in this round or in the previous one. A device that has not run yet,
 * or is switched off, has shared nothing; and two devices only hear each other
 * inside the same branch of an `if` (alignment).
 *
 * Neighbors are the devices within range, and the range shrinks as devices are
 * added: however many devices there are, each one hears only a few.
 */

export const SIZE = 6; // devices on each side of the lattice the walkthrough starts with
export const SPAN = SIZE - 1; // the arena is the square [0, SPAN] x [0, SPAN]
export const FEWEST = SIZE * SIZE; // the starting lattice
export const MOST = 100; // the arena takes this many devices at most
export const TEMPERATURE = { min: 16, max: 27 };
export const HOT = 22; // the threshold of `temperature > HOT`, in °C
export const CAP = 10; // the rounds a device counts at most
const LATTICE_RANGE = 1.65; // in the starting lattice, the 8 devices around, diagonals included
const LATTICE_HOLE = 0.42; // in the starting lattice, the space a switched-off device leaves empty

/** The temperature of the environment at (x, y), in °C: two warm spots on a cool floor. */
export function temperature(x, y) {
  const spot = (cx, cy, spread) => Math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / spread);
  return TEMPERATURE.min + 11 * spot(1.4, 3.6, 1.8) + 7 * spot(3.9, 1.3, 1.1);
}

/** A small seeded generator of numbers in [0, 1) (mulberry32), so that every visit looks the same. */
export function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = Math.imul(state ^ (state >>> 15), state | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

function jitter(seed) {
  const noise = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return noise - Math.floor(noise) - 0.5;
}

/**
 * Where the devices sit: a deformed lattice, then every further device in the
 * widest gap left (best candidate sampling). Adding devices never moves the others.
 */
export const PLACES = (() => {
  const places = [];
  for (let row = 0; row < SIZE; row += 1) {
    for (let col = 0; col < SIZE; col += 1) {
      const inner = row > 0 && row < SPAN && col > 0 && col < SPAN;
      const id = row * SIZE + col;
      places.push({ x: col + (inner ? 0.25 * jitter(id) : 0), y: row + (inner ? 0.25 * jitter(id + 99) : 0) });
    }
  }
  const random = seeded(7);
  while (places.length < MOST) {
    let best = null;
    let widest = -1;
    for (let candidate = 0; candidate < 40; candidate += 1) {
      const place = { x: random() * SPAN, y: random() * SPAN };
      const gap = Math.min(...places.map((other) => Math.hypot(other.x - place.x, other.y - place.y)));
      if (gap > widest) {
        best = place;
        widest = gap;
      }
    }
    places.push(best);
  }
  return places;
})();

/**
 * The communication radius of `count` devices. It shrinks a little faster than
 * their spacing, as the devices added in the gaps spread more evenly than a
 * lattice: an inner device keeps hearing 6 to 10 neighbors, from 36 devices to 100.
 */
function rangeOf(count) {
  return LATTICE_RANGE * (FEWEST / count) ** 0.58;
}

/**
 * The first `count` devices at `places` (PLACES, unless they were moved), their
 * `range` (rangeOf(count), unless it is given) and the `hole` a switched-off one
 * leaves, who is in range of whom, and how many neighbors a device far from the
 * border has (`typical`, the median, to scale their counts).
 */
export function createNetwork(count = FEWEST, places = PLACES, range = rangeOf(count)) {
  const hole = LATTICE_HOLE * Math.sqrt(FEWEST / count);
  const devices = places.slice(0, count).map((place, id) => ({ id, ...place }));
  const links = [];
  const inRange = devices.map(() => []);
  for (const a of devices) {
    for (const b of devices) {
      const length = Math.hypot(a.x - b.x, a.y - b.y);
      if (a.id < b.id && length <= range) {
        links.push({ a: a.id, b: b.id, length });
        inRange[a.id].push({ id: b.id, length });
        inRange[b.id].push({ id: a.id, length });
      }
    }
  }
  inRange.forEach((list) => list.sort((p, q) => p.id - q.id));
  const away = (value) => value >= range && value <= SPAN - range;
  const inner = devices.filter((device) => away(device.x) && away(device.y));
  const counts = (inner.length > 0 ? inner : devices).map((device) => inRange[device.id].length).sort((a, b) => a - b);
  return { devices, links, inRange, range, hole, typical: counts[Math.floor(counts.length / 2)] };
}

/** The state of every device before the first round: nobody has run, nobody has shared. */
export function initialStates(network) {
  return network.devices.map(() => null);
}

/** The ids of `count` devices in random order: who runs first in a round. */
export function shuffled(count, random) {
  const order = Array.from({ length: count }, (_, id) => id);
  for (let index = count - 1; index > 0; index -= 1) {
    const other = Math.floor(random() * (index + 1));
    [order[index], order[other]] = [order[other], order[index]];
  }
  return order;
}

/** What device `id` computes when it runs, from what the others last shared. */
export function fire(network, environment, states, id) {
  return environment.off.has(id) ? null : runDevice(network, environment, states, network.devices[id]);
}

const NOWHERE = { distance: Infinity, via: null };
const HERE = { distance: 0, via: null };

/** distance_to: the best estimate through the neighbors, min of (their estimate + distance to them). */
function through(neighbors, shared, estimateOf) {
  let best = NOWHERE;
  for (const { id, length } of neighbors) {
    const distance = estimateOf(shared[id]) + length;
    if (distance < best.distance) {
      best = { distance, via: id };
    }
  }
  return best;
}

/**
 * The broadcast inside distance_between: the value of the neighbor closest to the
 * source, or the device's own value until a neighbor has heard of the source.
 */
function relay(neighbors, shared, own) {
  let best = { distance: Infinity, value: own, via: null };
  for (const { id, length } of neighbors) {
    const { distance, value } = shared[id].between;
    if (distance + length < best.distance) {
      best = { distance: distance + length, value, via: id };
    }
  }
  return best;
}

/** One run of a device, on `shared`: what every device shared last. */
function runDevice(network, environment, shared, device) {
  const { id } = device;
  const source = environment.source === id;
  const target = environment.target === id;
  // Only the neighbors that have already run have shared something.
  const heard = network.inRange[id].filter((neighbor) => shared[neighbor.id] !== null);

  // remember(0), then set_count(min(count + 1, CAP)): the device's own last state,
  // none for a device that has not run yet or was switched off.
  const rounds = Math.min((shared[id]?.rounds ?? 0) + 1, CAP);

  const toTarget = target ? HERE : through(heard, shared, (state) => state.toTarget.distance);
  const toSource = source ? HERE : through(heard, shared, (state) => state.toSource.distance);

  // The channel: distance_between broadcasts the source's distance to the target. By the
  // triangle inequality, no trip through a device is shorter: the channel keeps the devices
  // through which it is at most `width` longer.
  const between = source ? { distance: 0, value: toTarget.distance, via: null } : relay(heard, shared, toTarget.distance);
  const inChannel = toSource.distance + toTarget.distance <= between.value + environment.width;

  // if in_channel: ... else: ... — only the neighbors that took the same branch answer.
  const branch = inChannel ? "inside" : "outside";
  const sameBranch = heard.filter((neighbor) => shared[neighbor.id].branch === branch);
  const split = source ? HERE : through(sameBranch, shared, (state) => state.split.distance);

  return {
    temperature: temperature(device.x, device.y),
    rounds,
    heard: heard.map((neighbor) => neighbor.id),
    toTarget,
    toSource,
    between,
    inChannel,
    branch,
    sameBranch: sameBranch.map((neighbor) => neighbor.id),
    split,
  };
}

const close = (a, b) => a === b || Math.abs(a - b) < 1e-9;
const SAME = {
  temperature: close,
  rounds: (a, b) => a === b,
  heard: (a, b) => a.length === b.length && a.every((id, index) => id === b[index]),
  toTarget: (a, b) => close(a.distance, b.distance),
  toSource: (a, b) => close(a.distance, b.distance),
  between: (a, b) => close(a.distance, b.distance) && close(a.value, b.value),
  branch: (a, b) => a === b,
  split: (a, b) => close(a.distance, b.distance),
};

/** Whether a round changed none of `fields` (keys of a device state): the program reached its fixpoint. */
export function isStable(previous, next, fields) {
  return next.every((state, id) => {
    const before = previous[id];
    if (state === null || before === null) {
      return state === before;
    }
    return fields.every((field) => SAME[field](state[field], before[field]));
  });
}

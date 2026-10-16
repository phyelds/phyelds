/*
 * The fields of the walkthrough at infinite density.
 *
 * With a device at every point of the arena, each program converges to a
 * continuous field: the exact distance instead of its estimate along the
 * links, the shortest curve instead of a chain of devices. They are computed
 * on a fine grid, and only the parts that a change of the environment affects.
 */
import { SPAN, temperature } from "./model.js";

export const RESOLUTION = 61; // grid points on each side
const SPACING = SPAN / (RESOLUTION - 1);
const SHARE_SAMPLES = 256; // points of the communication disc used to measure its share

// Grid moves of up to three cells in every direction without a common divisor: 32
// directions, so that distances along the grid stay within 1% of straight lines.
const STENCIL = (() => {
  const gcd = (a, b) => (b === 0 ? a : gcd(b, a % b));
  const moves = [];
  for (let dr = -3; dr <= 3; dr += 1) {
    for (let dc = -3; dc <= 3; dc += 1) {
      if ((dr || dc) && gcd(Math.abs(dr), Math.abs(dc)) === 1) {
        moves.push({ dr, dc, length: Math.hypot(dr, dc) * SPACING });
      }
    }
  }
  return moves;
})();

/** Points of the unit disc spread evenly (a sunflower pattern). */
const DISC = Array.from({ length: SHARE_SAMPLES }, (_, k) => {
  const radius = Math.sqrt((k + 0.5) / SHARE_SAMPLES);
  const angle = k * Math.PI * (3 - Math.sqrt(5));
  return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
});

/** The points of the grid, row by row. */
function createGrid() {
  const count = RESOLUTION * RESOLUTION;
  const x = new Float32Array(count);
  const y = new Float32Array(count);
  for (let index = 0; index < count; index += 1) {
    x[index] = (index % RESOLUTION) * SPACING;
    y[index] = Math.floor(index / RESOLUTION) * SPACING;
  }
  return { x, y, count };
}

function insideHole(x, y, holes) {
  return holes.some((hole) => Math.hypot(x - hole.x, y - hole.y) < hole.radius);
}

/** Whether the segment from a to b keeps out of every hole. */
function clear(ax, ay, bx, by, holes) {
  for (const hole of holes) {
    const dx = bx - ax;
    const dy = by - ay;
    const along = dx * dx + dy * dy;
    const t = along === 0 ? 0 : Math.max(0, Math.min(1, ((hole.x - ax) * dx + (hole.y - ay) * dy) / along));
    if (Math.hypot(ax + t * dx - hole.x, ay + t * dy - hole.y) < hole.radius) {
      return false;
    }
  }
  return true;
}

class MinHeap {
  constructor() {
    this.items = [];
  }

  get size() {
    return this.items.length;
  }

  push(index, value) {
    const items = this.items;
    items.push({ index, value });
    let child = items.length - 1;
    while (child > 0) {
      const parent = (child - 1) >> 1;
      if (items[parent].value <= items[child].value) break;
      [items[parent], items[child]] = [items[child], items[parent]];
      child = parent;
    }
  }

  pop() {
    const items = this.items;
    const top = items[0];
    const last = items.pop();
    if (items.length > 0) {
      items[0] = last;
      let parent = 0;
      for (;;) {
        const left = 2 * parent + 1;
        const right = left + 1;
        let smallest = parent;
        if (left < items.length && items[left].value < items[smallest].value) smallest = left;
        if (right < items.length && items[right].value < items[smallest].value) smallest = right;
        if (smallest === parent) break;
        [items[parent], items[smallest]] = [items[smallest], items[parent]];
        parent = smallest;
      }
    }
    return top;
  }
}

/**
 * Geodesic distance from the seeds, moving only through allowed points and
 * around the holes. A seed is a grid point with its exact distance already known.
 */
function geodesic(grid, allowed, seeds, holes) {
  const distance = new Float64Array(grid.count).fill(Infinity);
  const previous = new Int32Array(grid.count).fill(-1);
  const heap = new MinHeap();
  for (const { index, value } of seeds) {
    if (value < distance[index]) {
      distance[index] = value;
      heap.push(index, value);
    }
  }
  while (heap.size > 0) {
    const { index, value } = heap.pop();
    if (value > distance[index]) continue;
    const row = Math.floor(index / RESOLUTION);
    const col = index % RESOLUTION;
    for (const { dr, dc, length } of STENCIL) {
      const nextRow = row + dr;
      const nextCol = col + dc;
      if (nextRow < 0 || nextRow >= RESOLUTION || nextCol < 0 || nextCol >= RESOLUTION) continue;
      const next = nextRow * RESOLUTION + nextCol;
      const candidate = value + length;
      if (!allowed[next] || candidate >= distance[next]) continue;
      if (!clear(grid.x[index], grid.y[index], grid.x[next], grid.y[next], holes)) continue;
      distance[next] = candidate;
      previous[next] = index;
      heap.push(next, candidate);
    }
  }
  return { distance, previous };
}

/** Seeds for a distance from a point: every allowed grid point within `reach` that sees it. */
function seedsFromPoint(grid, allowed, point, holes, reach = Infinity) {
  const seeds = [];
  for (let index = 0; index < grid.count; index += 1) {
    const value = Math.hypot(grid.x[index] - point.x, grid.y[index] - point.y);
    if (allowed[index] && value <= reach && clear(point.x, point.y, grid.x[index], grid.y[index], holes)) {
      seeds.push({ index, value });
    }
  }
  return seeds;
}

/**
 * The shortest curve from `from` to the point the `toward` distance is measured
 * from, and its length; just `from` when the holes wall it off, as the source
 * alone is then on the path.
 */
function shortestPath(grid, toward, from, to, holes) {
  let start = -1;
  let length = Infinity;
  for (let index = 0; index < grid.count; index += 1) {
    const total = Math.hypot(grid.x[index] - from.x, grid.y[index] - from.y) + toward.distance[index];
    if (total < length && clear(from.x, from.y, grid.x[index], grid.y[index], holes)) {
      length = total;
      start = index;
    }
  }
  if (start < 0) return { points: [from], length };
  const chain = [from];
  for (let index = start; index >= 0; index = toward.previous[index]) {
    chain.push({ x: grid.x[index], y: grid.y[index] });
  }
  chain.push(to);
  return { points: pullTight(chain, holes), length };
}

/** Straighten a chain of points into the taut string through the same gaps. */
function pullTight(chain, holes) {
  const tight = [chain[0]];
  let anchor = 0;
  while (anchor < chain.length - 1) {
    let next = chain.length - 1;
    while (next > anchor + 1 && !clear(chain[anchor].x, chain[anchor].y, chain[next].x, chain[next].y, holes)) {
      next -= 1;
    }
    tight.push(chain[next]);
    anchor = next;
  }
  return tight;
}

function mapGrid(grid, free, valueAt) {
  const values = new Float32Array(grid.count);
  for (let index = 0; index < grid.count; index += 1) {
    values[index] = free[index] ? valueAt(index) : NaN;
  }
  return values;
}

/** Share of the communication disc around each point that lies in the free space. */
function neighborShare(grid, free, holes, range) {
  return mapGrid(grid, free, (index) => {
    let inside = 0;
    for (const offset of DISC) {
      const x = grid.x[index] + range * offset.x;
      const y = grid.y[index] + range * offset.y;
      if (x >= 0 && x <= SPAN && y >= 0 && y <= SPAN && !insideHole(x, y, holes)) inside += 1;
    }
    return inside / DISC.length;
  });
}

/** Where along the edge from grid point a to grid point b the field crosses `limit`. */
function crossing(grid, values, a, b, limit) {
  const t = Number.isFinite(values[a]) && Number.isFinite(values[b]) ? (limit - values[a]) / (values[b] - values[a]) : 0.5;
  return { x: grid.x[a] + t * (grid.x[b] - grid.x[a]), y: grid.y[a] + t * (grid.y[b] - grid.y[a]) };
}

/**
 * The region where `values` are at most `limit`, by marching squares: the piece
 * of it in every cell of the grid, to fill, and the segments of its outline.
 */
export function region(grid, values, limit) {
  const pieces = [];
  const outline = [];
  const within = (index) => values[index] <= limit;
  for (let row = 0; row < RESOLUTION - 1; row += 1) {
    for (let col = 0; col < RESOLUTION - 1; col += 1) {
      const corner = row * RESOLUTION + col;
      const corners = [corner, corner + 1, corner + RESOLUTION + 1, corner + RESOLUTION];
      const inside = corners.map(within);
      if (!inside.some(Boolean)) continue;
      const piece = [];
      const crossings = [];
      corners.forEach((index, k) => {
        const next = (k + 1) % 4;
        if (inside[k]) piece.push({ x: grid.x[index], y: grid.y[index] });
        if (inside[k] !== inside[next]) {
          const point = crossing(grid, values, index, corners[next], limit);
          piece.push(point);
          crossings.push(point);
        }
      });
      pieces.push(piece);
      for (let k = 0; k + 1 < crossings.length; k += 2) outline.push([crossings[k], crossings[k + 1]]);
    }
  }
  return { pieces, outline };
}

/**
 * The fields at infinite density for the current environment. `update` only
 * recomputes what changed: moving the target, say, leaves the temperature alone.
 */
export function createContinuum() {
  const grid = createGrid();
  const fields = { grid };
  const keys = {};

  function changed(name, key) {
    if (keys[name] === key) return false;
    keys[name] = key;
    return true;
  }

  function update(environment, network) {
    const position = (id) => network.devices[id];
    const holes = [...environment.off].sort((a, b) => a - b).map((id) => ({ ...position(id), radius: network.hole }));
    const holesKey = holes.map((hole) => `${hole.x},${hole.y},${hole.radius}`).join(";");
    const source = position(environment.source);
    const target = position(environment.target);

    if (changed("space", `${holesKey}|${network.range}`)) {
      fields.free = Uint8Array.from({ length: grid.count }, (_, index) => !insideHole(grid.x[index], grid.y[index], holes));
      fields.temperature = mapGrid(grid, fields.free, (index) => temperature(grid.x[index], grid.y[index]));
      fields.share = neighborShare(grid, fields.free, holes, network.range);
    }
    const { free } = fields;
    const distanceFrom = (point) => geodesic(grid, free, seedsFromPoint(grid, free, point, holes), holes);
    if (changed("toTarget", `${holesKey}|${environment.target}`)) {
      fields.toTargetSearch = distanceFrom(target);
      fields.toTarget = mapGrid(grid, free, (index) => fields.toTargetSearch.distance[index]);
    }
    if (changed("toSource", `${holesKey}|${environment.source}`)) {
      const toSource = distanceFrom(source).distance;
      fields.toSource = mapGrid(grid, free, (index) => toSource[index]);
    }
    if (changed("path", `${keys.toTarget}|${environment.source}`)) {
      const path = shortestPath(grid, fields.toTargetSearch, source, target, holes);
      fields.path = path.points;
      fields.between = path.length;
      fields.sum = mapGrid(grid, free, (index) => fields.toSource[index] + fields.toTarget[index]);
    }
    if (changed("split", `${keys.path}|${environment.width}`)) {
      const inside = Uint8Array.from(fields.sum, (sum) => sum <= fields.between + environment.width);
      const reach = 3 * SPACING;
      const split = geodesic(grid, inside, seedsFromPoint(grid, inside, source, holes, reach), holes).distance;
      fields.split = mapGrid(grid, inside, (index) => split[index]);
    }
    return fields;
  }

  return { grid, fields, update };
}

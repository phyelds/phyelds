/*
 * The 3D view: the arena on the ground, every device lifted to the height of
 * its value, and around them the cloud, the same field at infinite density.
 *
 * The scene only draws: walkthrough.js decides what each device, link and
 * point looks like, and passes it as a frame. The playground draws several
 * fields of the same devices at once, as layers stacked on top of each other.
 */
import { SPAN } from "./model.js";
import { rgba } from "./palette.js";

export const LIFT = 2.1; // world height of a value of 1

/** Traces an arrow of length `size` around (x, y), pointing at `angle` on the screen: a device heading there. */
export function traceArrow(context, x, y, size, angle) {
  const at = (length, turn) => [x + length * Math.cos(angle + turn), y + length * Math.sin(angle + turn)];
  context.moveTo(...at(size, 0));
  context.lineTo(...at(size * 0.85, 2.45));
  context.lineTo(...at(size * 0.35, Math.PI));
  context.lineTo(...at(size * 0.85, -2.45));
  context.closePath();
}
const insides = new WeakMap(); // the polygons of each shape, worked out once

/**
 * The inside of a shape given by its signed distance at the corners of a grid (`low`,
 * `high`, `cells`, `distances`): in each cell, the polygon where the distance is negative,
 * its border where the distance, interpolated along the sides, crosses zero.
 */
export function insideOf(shape) {
  if (insides.has(shape)) return insides.get(shape);
  const { low, high, cells, distances } = shape;
  const step = (high - low) / cells;
  const at = (i, j) => ({ x: low + i * step, y: low + j * step, d: distances[j * (cells + 1) + i] });
  const polygons = [];
  for (let j = 0; j < cells; j += 1) {
    for (let i = 0; i < cells; i += 1) {
      const corners = [at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)];
      const polygon = [];
      corners.forEach((corner, k) => {
        const next = corners[(k + 1) % 4];
        if (corner.d <= 0) polygon.push(corner);
        if (corner.d <= 0 !== next.d <= 0) {
          const t = corner.d / (corner.d - next.d);
          polygon.push({ x: corner.x + t * (next.x - corner.x), y: corner.y + t * (next.y - corner.y) });
        }
      });
      if (polygon.length >= 3) polygons.push(polygon);
    }
  }
  insides.set(shape, polygons);
  return polygons;
}

export const HIDDEN = 255; // colour index of a cloud point without a value
export const PULSE_MS = 320; // how long the ring of a device that just ran lasts
const DISTANCE = 15; // from the camera to the pivot
const FOV = 0.5; // vertical field of view, in radians
const PIVOT = { x: SPAN / 2, y: SPAN / 2, z: 0.75 };
// From the front, slightly to the right: near is down on the 2D map, as in the 3D view.
const HOME = { yaw: -Math.PI / 2 + 0.5, pitch: 0.58, zoom: 1 };
const PITCH_LIMITS = [0.12, 1.45];
const ZOOM_LIMITS = [0.6, 2.4];
const PAD = 0.45; // the ground extends this much beyond the outermost devices

const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z;
const cross = (a, b) => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x });
const unit = (a) => {
  const norm = Math.hypot(a.x, a.y, a.z);
  return { x: a.x / norm, y: a.y / norm, z: a.z / norm };
};

// Links fade as devices are added (`density` is 1 with the starting lattice), so that many stay a mesh.
const LINK_STYLES = {
  plain: (palette, density) => ({ color: rgba(palette.ink, 0.2 * density), width: 1 }),
  faint: (palette, density) => ({ color: rgba(palette.ink, 0.1 * density), width: 1 }),
  inside: (palette, density) => ({ color: rgba(palette.ink, 0.34 * density), width: 1.2 }),
  outside: (palette, density) => ({ color: rgba(palette.ink, 0.12 * density), width: 1 }),
  cut: (palette) => ({ color: rgba(palette.muted, 0.55), width: 1, dash: [2, 4] }),
  neighbor: (palette) => ({ color: rgba(palette.ink, 0.75), width: 1.5 }),
  via: (palette) => ({ color: rgba(palette.ink, 0.95), width: 2.8 }),
};

export function createScene(canvas) {
  const context = canvas.getContext("2d");
  const camera = { ...HOME };
  let size = { width: 1, height: 1 };
  let lens = null;
  let pivot = PIVOT; // what the camera looks at, and how far it backs away to fit a stack of layers
  let reach = 1;
  let margin = 0; // how far the world goes beyond the arena, on every side, where devices may move
  let projected = []; // every device drawn, as {id, x, y, z}, the topmost first
  let buckets = { colors: null, lists: [] };

  function resize() {
    const box = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    size = { width: Math.max(1, box.width), height: Math.max(1, box.height) };
    canvas.width = Math.round(size.width * ratio);
    canvas.height = Math.round(size.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function aim() {
    const { yaw, pitch, zoom } = camera;
    const eye = {
      x: pivot.x + DISTANCE * Math.cos(pitch) * Math.cos(yaw),
      y: pivot.y + DISTANCE * Math.cos(pitch) * Math.sin(yaw),
      z: pivot.z + DISTANCE * Math.sin(pitch),
    };
    const forward = unit(sub(pivot, eye));
    const right = unit(cross(forward, { x: 0, y: 0, z: 1 }));
    const up = cross(right, forward);
    const fit = Math.min(size.width, size.height * 1.3);
    const focal = (zoom * 0.5 * fit) / Math.tan(FOV / 2) / 1.45 / reach;
    lens = { eye, forward, right, up, focal, cx: size.width / 2, cy: size.height * 0.5 };
  }

  function project(x, y, z) {
    const { eye, forward, right, up, focal, cx, cy } = lens;
    const v = { x: x - eye.x, y: y - eye.y, z: z - eye.z };
    const depth = dot(v, forward);
    const scale = focal / depth;
    return { x: cx + dot(v, right) * scale, y: cy - dot(v, up) * scale, depth, scale: (scale * DISTANCE) / focal };
  }

  /** The point of the plane at height z under the pixel (px, py), or null if the plane is not there. */
  function groundAt(px, py, z = 0) {
    aim();
    const { eye, forward, right, up, focal, cx, cy } = lens;
    const sx = (px - cx) / focal;
    const sy = -(py - cy) / focal;
    const direction = {
      x: forward.x + right.x * sx + up.x * sy,
      y: forward.y + right.y * sx + up.y * sy,
      z: forward.z + right.z * sx + up.z * sy,
    };
    const t = (z - eye.z) / direction.z;
    if (!(t > 0 && t < Infinity)) return null;
    return { x: eye.x + t * direction.x, y: eye.y + t * direction.y };
  }

  /** Adds a polygon to the current path. */
  function polygon([first, ...rest], close = true) {
    context.moveTo(first.x, first.y);
    for (const point of rest) context.lineTo(point.x, point.y);
    if (close) context.closePath();
  }

  function circle(x, y, z, radius) {
    return Array.from({ length: 48 }, (_, k) => {
      const angle = (k / 48) * 2 * Math.PI;
      return project(x + radius * Math.cos(angle), y + radius * Math.sin(angle), z);
    });
  }

  /** The inside of `shape`, filled on the plane at height z: the shape a swarm takes. */
  function drawShape(shape, z, palette) {
    context.beginPath();
    for (const piece of insideOf(shape)) polygon(piece.map(({ x, y }) => project(x, y, z)));
    // One fill for every piece, so that their shared edges leave no seams.
    context.fillStyle = rgba(palette.rgb[palette.on], palette.dark ? 0.22 : 0.16);
    context.fill("nonzero");
  }

  /** The arena as a plane at height z, its edge as opaque as `edge`; returns its corners on screen. */
  function drawGround(palette, z = 0, edge = 0.14) {
    const corners = [
      project(-PAD - margin, -PAD - margin, z),
      project(SPAN + PAD + margin, -PAD - margin, z),
      project(SPAN + PAD + margin, SPAN + PAD + margin, z),
      project(-PAD - margin, SPAN + PAD + margin, z),
    ];
    context.beginPath();
    polygon(corners);
    context.fillStyle = rgba(palette.ink, palette.dark ? 0.035 : 0.03);
    context.fill();
    context.strokeStyle = rgba(palette.ink, edge);
    context.lineWidth = 1;
    context.stroke();
    return corners;
  }

  function drawHoles(frame) {
    const { palette } = frame;
    for (const device of frame.devices) {
      if (!device.off) continue;
      context.beginPath();
      polygon(circle(device.x, device.y, 0, frame.network.hole));
      context.fillStyle = rgba(palette.ink, 0.05);
      context.fill();
      context.setLineDash([3, 3]);
      context.strokeStyle = rgba(palette.muted, 0.7);
      context.stroke();
      context.setLineDash([]);
    }
  }

  /** The communication range of the focused device, at its height, around its neighbors. */
  function drawRange(frame) {
    const { focus, palette, devices } = frame;
    if (!focus || !focus.range) return;
    const device = devices[focus.id];
    context.beginPath();
    polygon(circle(device.x, device.y, device.z, frame.network.range));
    context.fillStyle = rgba(palette.ink, 0.05);
    context.fill();
    context.setLineDash([4, 4]);
    context.strokeStyle = rgba(palette.ink, 0.5);
    context.lineWidth = 1.2;
    context.stroke();
    context.setLineDash([]);
  }

  function drawStems(frame, points) {
    const { palette } = frame;
    context.lineWidth = 1;
    for (const device of frame.devices) {
      if (device.off) continue;
      const foot = project(device.x, device.y, 0);
      const top = points[device.id];
      const focused = frame.focus?.id === device.id || frame.selected === device.id;
      context.strokeStyle = rgba(palette.ink, focused ? 0.45 : 0.08);
      context.beginPath();
      context.moveTo(foot.x, foot.y);
      context.lineTo(top.x, top.y);
      context.stroke();
      context.fillStyle = rgba(palette.ink, 0.28);
      context.fillRect(foot.x - 1, foot.y - 1, 2, 2);
    }
  }

  /** A region of the arena at height z, cell by cell, in one path: filled at once, it shows no seams. */
  function regionPath(water, z) {
    context.beginPath();
    for (const piece of water.pieces) polygon(piece.map((point) => project(point.x, point.y, z)));
  }

  function outlinePath(water, z) {
    context.beginPath();
    for (const [a, b] of water.outline) {
      const from = project(a.x, a.y, z);
      const to = project(b.x, b.y, z);
      context.moveTo(from.x, from.y);
      context.lineTo(to.x, to.y);
    }
  }

  /** The flood seen from straight above, on the ground: the devices standing in it form the channel. */
  function drawShadow(frame) {
    const water = frame.cloud?.water;
    if (!water) return;
    const { palette } = frame;
    regionPath(water, 0);
    context.fillStyle = rgba(palette.rgb[palette.on], palette.dark ? 0.16 : 0.12);
    context.fill();
    outlinePath(water, 0);
    context.strokeStyle = rgba(palette.rgb[palette.on], 0.55);
    context.lineWidth = 1;
    context.stroke();
  }

  /** The water filling the valley of the cloud up to its level, with its shore and its name. */
  function drawWater(frame) {
    const water = frame.cloud?.water;
    if (!water) return;
    const { palette } = frame;
    const z = water.height * LIFT;
    regionPath(water, z);
    context.fillStyle = rgba(palette.rgb[palette.on], palette.dark ? 0.3 : 0.24);
    context.fill();
    outlinePath(water, z);
    context.strokeStyle = rgba(palette.rgb[palette.on], 0.95);
    context.lineWidth = 2;
    context.stroke();
    // The name sits above the far shore, away from the source and the target at the ends.
    const shore = water.outline.flat().map((point) => project(point.x, point.y, z));
    if (shore.length === 0) return;
    const farthest = shore.reduce((best, point) => (point.y < best.y ? point : best));
    context.font = `500 11.5px ${palette.mono}`;
    context.fillStyle = rgba(palette.rgb[palette.on]);
    context.textAlign = "center";
    context.fillText(water.label, farthest.x, farthest.y - 9);
  }

  function sortBuckets(cloud) {
    if (buckets.colors === cloud.color) return buckets.lists;
    const lists = new Map();
    cloud.color.forEach((color, index) => {
      if (color === HIDDEN) return;
      if (!lists.has(color)) lists.set(color, []);
      lists.get(color).push(index);
    });
    buckets = { colors: cloud.color, lists: [...lists] };
    return buckets.lists;
  }

  function drawCloud(frame) {
    const { cloud, palette } = frame;
    if (!cloud) return;
    context.globalAlpha = palette.dark ? 0.5 : 0.55;
    for (const [color, indices] of sortBuckets(cloud)) {
      context.fillStyle = palette.css[color];
      for (const index of indices) {
        const point = project(cloud.x[index], cloud.y[index], cloud.z[index]);
        const side = Math.max(1, 1.7 * point.scale);
        context.fillRect(point.x - side / 2, point.y - side / 2, side, side);
      }
    }
    context.globalAlpha = 1;
    if (cloud.curve) {
      // Dotted, as the rest of the cloud: the curve the network would follow at infinite density.
      context.beginPath();
      polygon(
        cloud.curve.map((point) => project(point.x, point.y, point.z)),
        false,
      );
      context.strokeStyle = palette.css[cloud.curveColor];
      context.lineWidth = 2.6;
      context.lineCap = "round";
      context.setLineDash([0.1, 4.5]);
      context.stroke();
      context.setLineDash([]);
      context.lineCap = "butt";
    }
  }

  function drawLinks(frame, links, points) {
    for (const link of links) {
      const style = LINK_STYLES[link.style](frame.palette, frame.density);
      const a = points[link.a];
      const b = points[link.b];
      context.strokeStyle = style.color;
      context.lineWidth = style.width;
      context.setLineDash(style.dash ?? []);
      context.beginPath();
      context.moveTo(a.x, a.y);
      context.lineTo(b.x, b.y);
      context.stroke();
    }
    context.setLineDash([]);
  }

  function drawDevice(frame, device, point) {
    const { palette, focus, selected } = frame;
    const radius = Math.max(2.6, Math.min(8, 5.4 * point.scale * frame.density));
    context.beginPath();
    if (device.off) {
      const arm = radius * 0.55;
      context.moveTo(point.x - arm, point.y - arm);
      context.lineTo(point.x + arm, point.y + arm);
      context.moveTo(point.x + arm, point.y - arm);
      context.lineTo(point.x - arm, point.y + arm);
      context.strokeStyle = rgba(palette.muted, 0.9);
      context.lineWidth = 1.4;
      context.stroke();
      return;
    }
    if (Number.isFinite(device.heading)) {
      // Where the heading points on the screen: a step along it, seen by the camera.
      const ahead = project(
        device.x + 0.25 * Math.cos(device.heading),
        device.y + 0.25 * Math.sin(device.heading),
        device.z,
      );
      traceArrow(context, point.x, point.y, radius * 1.7, Math.atan2(ahead.y - point.y, ahead.x - point.x));
    } else {
      context.arc(point.x, point.y, radius, 0, 2 * Math.PI);
    }
    if (device.color === null) {
      context.fillStyle = rgba(palette.stage);
      context.fill();
      context.strokeStyle = rgba(palette.muted, 0.85);
      context.lineWidth = 1.3;
      context.stroke();
    } else {
      context.fillStyle = palette.css[device.color];
      context.fill();
      context.strokeStyle = rgba(palette.stage, 0.9);
      context.lineWidth = 1.2;
      context.stroke();
    }
    const ring = (gap, color, width) => {
      context.beginPath();
      context.arc(point.x, point.y, radius + gap, 0, 2 * Math.PI);
      context.strokeStyle = color;
      context.lineWidth = width;
      context.stroke();
    };
    // A device that has just run sends out a ring: runs come one at a time, in random order.
    const age = frame.now - device.ranAt;
    if (frame.pulses && age >= 0 && age < PULSE_MS) {
      ring(1.5 + 9 * (age / PULSE_MS), rgba(palette.ink, 0.4 * (1 - age / PULSE_MS)), 1);
    }
    if (device.role) ring(3.5, rgba(palette.ink, 0.95), 1.6);
    if (focus && focus.id === device.id) ring(device.role ? 7 : 3.5, rgba(palette.ink), 2);
    else if (selected === device.id) ring(device.role ? 7 : 3.5, rgba(palette.ink, 0.45), 1.3);
    else if (focus && focus.neighbors.includes(device.id)) ring(2.5, rgba(palette.ink, 0.6), 1.1);
  }

  function tag(text, x, y, palette, emphasis = false) {
    context.font = `${emphasis ? 600 : 500} 11.5px ${palette.mono}`;
    const width = context.measureText(text).width + 12;
    const left = x - width / 2;
    const top = y - 21;
    context.beginPath();
    context.roundRect(left, top, width, 18, 9);
    context.fillStyle = rgba(palette.stage, 0.92);
    context.fill();
    context.strokeStyle = rgba(palette.ink, emphasis ? 0.6 : 0.22);
    context.lineWidth = 1;
    context.stroke();
    context.fillStyle = rgba(palette.ink);
    context.textAlign = "center";
    context.fillText(text, x, top + 13);
  }

  function draw(frame) {
    pivot = PIVOT;
    reach = 1;
    margin = 0;
    aim();
    context.clearRect(0, 0, size.width, size.height);
    const points = frame.devices.map((device) => project(device.x, device.y, device.z));
    drawGround(frame.palette);
    drawShadow(frame);
    drawHoles(frame);
    drawRange(frame);
    // Only the inspected device stands on a stem: one per device would clutter the field.
    const inspected = (device) => frame.focus?.id === device.id || frame.selected === device.id;
    drawStems({ ...frame, devices: frame.devices.filter(inspected) }, points);
    drawCloud(frame);
    drawWater(frame);
    drawLinks(frame, frame.links, points);
    drawLinks(frame, frame.highlights, points);
    const order = frame.devices.map((device) => device.id).sort((a, b) => points[b].depth - points[a].depth);
    for (const id of order) drawDevice(frame, frame.devices[id], points[id]);
    for (const device of frame.devices) {
      if (device.role) tag(device.role, points[device.id].x, points[device.id].y - 10, frame.palette);
    }
    if (frame.focus && frame.focus.label) {
      const point = points[frame.focus.id];
      tag(frame.focus.label, point.x, point.y - (frame.devices[frame.focus.id].role ? 32 : 10), frame.palette, true);
    }
    projected = points.map((point, id) => ({ id, x: point.x, y: point.y, z: frame.devices[id].z }));
  }

  /** The name of a layer, left of the corner of its plane that is leftmost on screen, shortened to fit. */
  function label(text, corners, palette, focused) {
    const left = corners.reduce((best, corner) => (corner.x < best.x ? corner : best));
    const room = left.x - 14;
    context.font = `${focused ? 600 : 500} 11.5px ${palette.mono}`;
    let shown = text;
    while (shown.length > 2 && context.measureText(shown).width > room) shown = `${shown.slice(0, -2)}…`;
    if (context.measureText(shown).width > room) return;
    context.fillStyle = rgba(palette.ink, focused ? 0.95 : 0.55);
    context.textAlign = "right";
    context.fillText(shown, left.x - 10, left.y + 4);
  }

  /**
   * Several fields of the same devices, each in a layer of its own, stacked from the
   * ground up: every layer of `frame.layers` has the height of its plane (`base`), its
   * `label`, `devices` (heights included), `links` and `highlights`, and one of them is
   * `focused`; `frame.top` is the height of the stack, which the camera frames. The
   * slabs must not overlap. A pillar joins the places in every layer of the device
   * under the pointer, and the source and the target are tagged on top.
   */
  function drawLayers(frame) {
    const { layers, palette, top } = frame;
    pivot = { ...PIVOT, z: top / 2 };
    margin = frame.margin ?? 0;
    reach = Math.max(1, (SPAN + 2 * margin + top) / (SPAN + LIFT));
    aim();
    context.clearRect(0, 0, size.width, size.height);
    const highest = layers[layers.length - 1];
    const tops = highest.devices.map((device) => project(device.x, device.y, device.z));
    // Stems from every device down to the ground would hide the values they hold up: only the
    // device under the pointer keeps one, to be found on the ground and in every layer.
    const stemmed = highest.devices.filter((device) => device.id === frame.focus?.id);
    drawStems({ ...frame, devices: stemmed }, tops);
    // Farthest from the eye first: at a low pitch, the camera sits inside a tall stack, and a
    // layer above the eye hides the ones above it, seen from below.
    const away = (k) => Math.abs(layers[k].base - lens.eye.z);
    const order = layers.map((_, k) => k).sort((a, b) => away(b) - away(a));
    const drawn = [];
    let focused = null;
    for (const k of order) {
      const layer = layers[k];
      const points = layer.devices.map((device) => project(device.x, device.y, device.z));
      label(layer.label, drawGround(palette, layer.base, layer.focused ? 0.4 : 0.14), palette, layer.focused);
      if (layer.shape) drawShape(layer.shape, layer.base, palette);
      drawLinks(frame, layer.links, points);
      drawLinks(frame, layer.highlights, points);
      // The rings of the neighbors and of the devices that just ran belong to the focused layer only.
      const looks = layer.focused
        ? frame
        : { ...frame, pulses: false, focus: frame.focus && { ...frame.focus, neighbors: [] } };
      const byDepth = layer.devices.map((device) => device.id).sort((a, b) => points[b].depth - points[a].depth);
      for (const id of byDepth) drawDevice(looks, layer.devices[id], points[id]);
      drawn.push(...points.map((point, id) => ({ id, x: point.x, y: point.y, z: layer.devices[id].z })));
      if (layer.focused) focused = { layer, points };
    }
    for (const device of highest.devices) {
      if (device.role) tag(device.role, tops[device.id].x, tops[device.id].y - 10, palette);
    }
    if (frame.focus && frame.focus.label && focused) {
      const point = focused.points[frame.focus.id];
      const tagged = focused.layer === highest && focused.layer.devices[frame.focus.id].role;
      tag(frame.focus.label, point.x, point.y - (tagged ? 32 : 10), palette, true);
    }
    // The topmost first: where two layers draw a device at the same pixel, the pointer picks the one on top.
    projected = drawn.reverse();
  }

  /** The device drawn under the pixel (px, py), and the height it is drawn at, or null. */
  function pickInstance(px, py) {
    let best = null;
    let bestDistance = 14;
    for (const point of projected) {
      const distance = Math.hypot(point.x - px, point.y - py);
      if (distance < bestDistance) {
        best = point;
        bestDistance = distance;
      }
    }
    return best && { id: best.id, z: best.z };
  }

  /** The device drawn under the pixel (px, py), if any. */
  function pick(px, py) {
    return pickInstance(px, py)?.id ?? null;
  }

  function orbit(dx, dy) {
    camera.yaw -= dx * 0.008;
    camera.pitch = Math.max(PITCH_LIMITS[0], Math.min(PITCH_LIMITS[1], camera.pitch + dy * 0.006));
  }

  function zoom(factor) {
    camera.zoom = Math.max(ZOOM_LIMITS[0], Math.min(ZOOM_LIMITS[1], camera.zoom * factor));
  }

  function reset() {
    Object.assign(camera, HOME);
  }

  return { camera, resize, draw, drawLayers, pick, pickInstance, groundAt, orbit, zoom, reset };
}

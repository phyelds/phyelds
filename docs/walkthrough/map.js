/*
 * The 2D view: the arena from above, the cloud as a smooth heat map under the
 * devices. A marker on its border shows where the camera of the 3D view stands.
 */
import { RESOLUTION } from "./continuum.js";
import { RANGE, SPAN } from "./model.js";
import { rgba } from "./palette.js";
import { HIDDEN } from "./scene.js";

const PAD = 14;
const LINK_ALPHA = { plain: 0.16, faint: 0.1, outside: 0.12, inside: 0.34, cut: 0.4 };

export function createMap(canvas) {
  const context = canvas.getContext("2d");
  const raster = document.createElement("canvas");
  raster.width = RESOLUTION;
  raster.height = RESOLUTION;
  const pixels = raster.getContext("2d");
  let size = { width: 1, height: 1 };
  let painted = { color: null, palette: null };
  let placed = [];

  function resize() {
    const box = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    size = { width: Math.max(1, box.width), height: Math.max(1, box.height) };
    canvas.width = Math.round(size.width * ratio);
    canvas.height = Math.round(size.height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function frameOfArena() {
    const side = Math.min(size.width, size.height) - 2 * PAD;
    return { left: (size.width - side) / 2, top: (size.height - side) / 2, side };
  }

  function toScreen(x, y) {
    const { left, top, side } = frameOfArena();
    return { x: left + (x / SPAN) * side, y: top + (1 - y / SPAN) * side };
  }

  /** The cloud as an image, one pixel per grid point, north up. */
  function paint(cloud, palette) {
    if (painted.color === cloud.color && painted.palette === palette) return;
    const image = pixels.createImageData(RESOLUTION, RESOLUTION);
    cloud.color.forEach((color, index) => {
      if (color === HIDDEN) return;
      const row = RESOLUTION - 1 - Math.floor(index / RESOLUTION);
      const offset = 4 * (row * RESOLUTION + (index % RESOLUTION));
      const [red, green, blue] = palette.rgb[color];
      image.data.set([red, green, blue, palette.dark ? 150 : 170], offset);
    });
    pixels.putImageData(image, 0, 0);
    painted = { color: cloud.color, palette };
  }

  function line(a, b, color, width, dash = []) {
    context.strokeStyle = color;
    context.lineWidth = width;
    context.setLineDash(dash);
    context.beginPath();
    context.moveTo(a.x, a.y);
    context.lineTo(b.x, b.y);
    context.stroke();
    context.setLineDash([]);
  }

  function drawCamera(frame) {
    const { left, top, side } = frameOfArena();
    const center = { x: left + side / 2, y: top + side / 2 };
    const reach = side / 2 + PAD * 0.55;
    // World y points up on the map, so the screen angle is the yaw mirrored.
    const angle = -frame.camera.yaw;
    const tip = { x: center.x + Math.cos(angle) * (reach - 5), y: center.y + Math.sin(angle) * (reach - 5) };
    const back = { x: center.x + Math.cos(angle) * (reach + 3), y: center.y + Math.sin(angle) * (reach + 3) };
    const normal = { x: -Math.sin(angle) * 4.5, y: Math.cos(angle) * 4.5 };
    context.beginPath();
    context.moveTo(tip.x, tip.y);
    context.lineTo(back.x + normal.x, back.y + normal.y);
    context.lineTo(back.x - normal.x, back.y - normal.y);
    context.closePath();
    context.fillStyle = rgba(frame.palette.ink, 0.55);
    context.fill();
  }

  function draw(frame) {
    const { palette, network } = frame;
    context.clearRect(0, 0, size.width, size.height);
    const { left, top, side } = frameOfArena();
    if (frame.cloud) {
      paint(frame.cloud, palette);
      context.imageSmoothingEnabled = true;
      context.drawImage(raster, left, top, side, side);
    }
    context.strokeStyle = rgba(palette.ink, 0.18);
    context.lineWidth = 1;
    context.strokeRect(left, top, side, side);

    const points = network.devices.map((device) => toScreen(device.x, device.y));
    for (const link of frame.links) {
      const alpha = LINK_ALPHA[link.style] * (link.style === "cut" ? 1 : frame.density);
      line(points[link.a], points[link.b], rgba(palette.ink, alpha), 1, link.style === "cut" ? [2, 3] : []);
    }
    if (frame.cloud && frame.cloud.water) {
      context.beginPath();
      for (const [a, b] of frame.cloud.water.outline) {
        const from = toScreen(a.x, a.y);
        const to = toScreen(b.x, b.y);
        context.moveTo(from.x, from.y);
        context.lineTo(to.x, to.y);
      }
      context.strokeStyle = palette.css[palette.on];
      context.lineWidth = 1.6;
      context.stroke();
    }
    if (frame.cloud && frame.cloud.curve) {
      context.beginPath();
      frame.cloud.curve.forEach((point, index) => {
        const screen = toScreen(point.x, point.y);
        if (index === 0) context.moveTo(screen.x, screen.y);
        else context.lineTo(screen.x, screen.y);
      });
      context.strokeStyle = palette.css[frame.cloud.curveColor];
      context.lineWidth = 2;
      context.lineCap = "round";
      context.setLineDash([0.1, 3.5]);
      context.stroke();
      context.setLineDash([]);
      context.lineCap = "butt";
    }
    if (frame.focus && frame.focus.range) {
      const center = points[frame.focus.id];
      context.beginPath();
      context.arc(center.x, center.y, (RANGE / SPAN) * side, 0, 2 * Math.PI);
      context.setLineDash([3, 3]);
      context.strokeStyle = rgba(palette.ink, 0.55);
      context.stroke();
      context.setLineDash([]);
    }
    for (const link of frame.highlights) {
      line(points[link.a], points[link.b], rgba(palette.ink, link.style === "via" ? 0.95 : 0.7), link.style === "via" ? 2.2 : 1.2);
    }

    const dot = Math.max(2, 3.4 * frame.density);
    for (const device of frame.devices) {
      const { x, y } = points[device.id];
      context.beginPath();
      if (device.off) {
        context.moveTo(x - 2.5, y - 2.5);
        context.lineTo(x + 2.5, y + 2.5);
        context.moveTo(x + 2.5, y - 2.5);
        context.lineTo(x - 2.5, y + 2.5);
        context.strokeStyle = rgba(palette.muted);
        context.lineWidth = 1.2;
        context.stroke();
        continue;
      }
      context.arc(x, y, dot, 0, 2 * Math.PI);
      context.fillStyle = device.color === null ? rgba(palette.stage) : palette.css[device.color];
      context.fill();
      context.strokeStyle = device.color === null ? rgba(palette.muted) : rgba(palette.stage, 0.9);
      context.lineWidth = 1;
      context.stroke();
      const ring = (radius, color, width) => {
        context.beginPath();
        context.arc(x, y, radius, 0, 2 * Math.PI);
        context.strokeStyle = color;
        context.lineWidth = width;
        context.stroke();
      };
      if (device.role) ring(dot + 2.6, rgba(palette.ink, 0.9), 1.3);
      if (frame.focus && frame.focus.id === device.id) ring(dot + (device.role ? 5 : 2.6), rgba(palette.ink), 1.6);
    }
    drawCamera(frame);
    placed = points;
  }

  /** The point of the arena under the pixel (px, py). */
  function worldAt(px, py) {
    const { left, top, side } = frameOfArena();
    return { x: ((px - left) / side) * SPAN, y: (1 - (py - top) / side) * SPAN };
  }

  /** The device drawn under the pixel (px, py), if any. */
  function pick(px, py) {
    let best = null;
    let bestDistance = 9;
    placed.forEach((point, id) => {
      const distance = Math.hypot(point.x - px, point.y - py);
      if (distance < bestDistance) {
        best = id;
        bestDistance = distance;
      }
    });
    return best;
  }

  return { resize, draw, pick, worldAt };
}

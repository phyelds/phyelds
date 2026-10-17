/*
 * Pointer gestures on a view of the network: hovering a device inspects it,
 * pressing it selects it, dragging a device that can be grabbed moves it, and
 * dragging anywhere else turns the view, when the view can turn.
 */

const DEAD_ZONE = 4; // pixels the pointer moves before a press becomes a drag

/** Where the pointer is, in pixels from the top left corner of `target`. */
function local(event, target) {
  const box = target.getBoundingClientRect();
  return { x: event.clientX - box.left, y: event.clientY - box.top };
}

/**
 * Binds the gestures to `canvas`. `pick(x, y)` is the device under a pixel, or null.
 * `grab(id, x, y)` is what dragging that device moves (a handle, read when the drag
 * starts), or null if it cannot be dragged; `drag(handle, x, y)` moves it to a pixel.
 * `orbit(dx, dy)`, if given, turns the view. `hover(id)` and `select(id)` report the
 * device under the pointer and the device pressed.
 */
export function bindPointer(canvas, { pick, grab, drag, orbit = null, hover, select }) {
  let gesture = null;
  const cursor = (id, at) => {
    const grabbable = id !== null && grab(id, at.x, at.y) !== null;
    canvas.classList.toggle("is-over-device", id !== null && !grabbable);
    canvas.classList.toggle("is-over-role", grabbable);
    canvas.classList.toggle("is-moving", gesture?.kind === "move");
    canvas.classList.toggle("is-orbiting", gesture?.kind === "orbit");
  };
  canvas.addEventListener("pointerdown", (event) => {
    canvas.setPointerCapture(event.pointerId);
    const at = local(event, canvas);
    const id = pick(at.x, at.y);
    const handle = id === null ? null : grab(id, at.x, at.y);
    let kind = orbit ? "orbit" : "none";
    if (id !== null) kind = handle === null ? "press" : "move";
    gesture = { kind, id, handle, ...at, moved: false };
    cursor(id, at);
  });
  canvas.addEventListener("pointermove", (event) => {
    const at = local(event, canvas);
    if (gesture === null) {
      const id = pick(at.x, at.y);
      hover(id);
      cursor(id, at);
      return;
    }
    const dx = at.x - gesture.x;
    const dy = at.y - gesture.y;
    if (!gesture.moved && Math.hypot(dx, dy) < DEAD_ZONE) return;
    gesture.moved = true;
    if (gesture.kind === "press" && orbit) gesture.kind = "orbit";
    if (gesture.kind === "orbit") {
      orbit(dx, dy);
      Object.assign(gesture, at);
    } else if (gesture.kind === "move") {
      drag(gesture.handle, at.x, at.y);
    }
    cursor(gesture.id, at);
  });
  const end = (event) => {
    if (gesture && !gesture.moved && gesture.id !== null) select(gesture.id);
    gesture = null;
    const at = local(event, canvas);
    cursor(pick(at.x, at.y), at);
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("pointerleave", () => {
    if (gesture === null) hover(null);
  });
}

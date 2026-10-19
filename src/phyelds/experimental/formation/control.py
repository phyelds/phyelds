"""
How robots move to spread over a shape: the lattice velocity (``LatticeVelocity.kt``),
Lloyd's coverage control on a Voronoi cell clipped to the shape (``VoronoiCell.kt``).
"""
from collections.abc import Callable, Sequence
import math

from phyelds.calculus import aggregate, remember
from phyelds.experimental.formation.shapes import Shape
from phyelds.experimental.swarm.vector import Vector

_DISK_SIDES = 32  # sides of the polygon that bounds a planar cell before the bisectors cut it
_SAMPLES = 8  # samples per side of the box of a cell
_OUTSIDE_PUSH = 0.5  # the largest push of the neighbors outside the shape, against its pull
_GRADIENT_STEP = 0.001


def _depth(point: Vector, cutting: Sequence[Vector], reach: float) -> float:
    """How deep ``point`` lies in the cell: its distance from the ball and every bisector."""
    depth = reach - point.length()
    for neighbor in cutting:
        depth = min(depth, (neighbor.dot(neighbor) / 2 - point.dot(neighbor)) / neighbor.length())
    return depth


def _cut(corners: list[Vector], neighbor: Vector) -> list[Vector]:
    """The convex polygon ``corners``, cut by the bisector between the device and ``neighbor``."""
    half = neighbor.dot(neighbor) / 2
    cut = []
    for index, start in enumerate(corners):
        end = corners[(index + 1) % len(corners)]
        margin_start, margin_end = half - start.dot(neighbor), half - end.dot(neighbor)
        if margin_start >= 0:
            cut.append(start)
        if margin_start * margin_end < 0:
            cut.append(start + (end - start) * (margin_start / (margin_start - margin_end)))
    return cut


def _planar_cell(offsets: Sequence[Vector], reach: float) -> tuple[list[Vector], list[Vector]]:
    """The corners of the planar cell, and the neighbors whose bisectors cut it."""
    angles = [2 * math.pi * side / _DISK_SIDES for side in range(_DISK_SIDES)]
    corners = [Vector(reach).rotate(angle) for angle in angles]
    cutting = []
    # From the nearest: once a bisector misses the cell, the farther ones miss it too.
    nearest_first = sorted([offset for offset in offsets if offset.length() > 0], key=Vector.length)
    for neighbor in nearest_first:
        radius = max((corner.length() for corner in corners), default=0.0)
        if neighbor.length() / 2 <= radius:
            corners = _cut(corners, neighbor)
            cutting.append(neighbor)
    return corners, cutting


def _grid(low: Vector, high: Vector, dimensions: int) -> tuple[list[Vector], float]:
    """The centers of a grid of ``_SAMPLES`` per side over a box, and the side of a pixel."""
    steps = (high - low) / _SAMPLES
    pixel = max(tuple(steps)[:dimensions])
    axes = [
        [start + (index + 0.5) * step for index in range(_SAMPLES)] if axis < dimensions else [0.0]
        for axis, (start, step) in enumerate(zip(low, steps))
    ]
    return [Vector(x, y, z) for x in axes[0] for y in axes[1] for z in axes[2]], pixel


def _box(points: Sequence[Vector]) -> tuple[Vector, Vector]:
    """The corners of the box of ``points``."""
    axes = list(zip(*points))
    return Vector(*(min(axis) for axis in axes)), Vector(*(max(axis) for axis in axes))


def _cell_box(
    offsets: Sequence[Vector], reach: float, dimensions: int
) -> tuple[Vector, Vector, list[Vector]] | None:
    """
    The box of the cell, and the neighbors that cut it. A planar cell always holds the
    disk around the device up to its nearest bisector; in space, ``None`` if the cell is
    too small for any sample of the ball.
    """
    if dimensions == 2:
        corners, cutting = _planar_cell([Vector(offset.x, offset.y) for offset in offsets], reach)
        return (*_box(corners), cutting)
    cutting = [offset for offset in offsets if 0 < offset.length() <= 2 * reach]
    coarse, pixel = _grid(Vector(-reach, -reach, -reach), Vector(reach, reach, reach), 3)
    inside = [point for point in coarse if _depth(point, cutting, reach) > -pixel / 2]
    if not inside:
        return None
    low, high = _box(inside)
    margin = Vector(pixel, pixel, pixel) / 2
    return low - margin, high + margin, cutting


def _weighted_centroid(
    samples: Sequence[Vector],
    pixel: float,
    cell_depth: Callable[[Vector], float],
    clip: Callable[[Vector], float] | None,
) -> Vector:
    """The centroid of the samples, weighted by how much of each pixel is in the cell and shape."""
    total, weight = Vector(), 0.0
    for point in samples:
        depth = cell_depth(point)
        if depth <= -pixel / 2:
            continue  # out of the cell, which spares evaluating the shape
        if clip is not None:
            depth = min(depth, clip(point))
        coverage = min(max(0.5 + depth / pixel, 0.0), 1.0)
        total, weight = total + point * coverage, weight + coverage
    return total / weight if weight > 0 else Vector()


def voronoi_centroid(
    shape: Shape,
    position: Vector,
    offsets: Sequence[Vector],
    reach: float,
    dimensions: int = 2,
) -> Vector:
    """
    The centroid of the Voronoi cell of the device, as an offset from it: the points
    within ``reach`` closer to the device than to any neighbor and, if the device is
    inside the shape, inside it. Each sample counts as much of its pixel as lies in the
    cell and the shape (anti-aliasing), so that the centroid moves smoothly.

    In the plane, as in ``VoronoiCell.kt``, the cell is a polygon cut by the bisectors and sampled
    on an 8 by 8 grid over its box; in space, the box is found by sampling the ball of
    ``reach`` first.

    Args:
        shape: The shape, in the frame of the device.
        position: The position of the device in that frame.
        offsets: The vectors from the device to its neighbors in that frame.
        reach: The radius of the cell: half the communication range, so that the
            neighbors that shape the cell are all in range.
        dimensions: 2 to spread in the horizontal plane, 3 in space.

    Returns:
        The centroid, relative to the device; zero for an empty cell.
    """
    cell = _cell_box(offsets, reach, dimensions)
    if cell is None:
        return Vector()
    low, high, cutting = cell
    samples, pixel = _grid(low, high, dimensions)
    # Outside the shape the whole cell counts: on its way in, the device still keeps apart.
    clip = None if shape(position) > 0 else (lambda point: -shape(position + point))
    return _weighted_centroid(samples, pixel, lambda point: _depth(point, cutting, reach), clip)


@aggregate
def _adaptive_step(control: Vector, decrease: float, increase: float, min_gain: float) -> float:
    """The step of Rprop: it shrinks when ``control`` reverses, and grows back while it holds."""
    set_step, step = remember((1.0, Vector()))
    gain, last_control = step.value
    if last_control.dot(control) < 0:
        gain = max(min_gain, gain * decrease)
    else:
        gain = min(1.0, gain * increase)
    set_step((gain, control))
    return gain


@aggregate
def lattice_velocity(  # pylint: disable=too-many-arguments
    shape: Shape,
    position: Vector,
    offsets: Sequence[Vector],
    *,
    reach: float,
    max_speed: float = 1.0,
    gain: float = 1.0,
    decrease: float = 0.5,
    increase: float = 1.2,
    min_gain: float = 0.05,
    dimensions: int = 2,
) -> Vector:
    """
    The velocity that spreads the swarm evenly over ``shape``.

    Inside the shape, the device heads to the centroid of its Voronoi cell clipped to the
    shape, which spreads the swarm and keeps it off the border. Outside, the shape pulls
    it in along the normal of its border, and the centroid pushes it aside, by at most
    half the pull and never back out. The speed adapts as in Rprop: the step shrinks when
    the direction reverses, an overshoot, and grows back while it holds.

    Args:
        shape: The shape, in the frame of the device.
        position: The position of the device in that frame.
        offsets: The vectors from the device to its neighbors in that frame.
        reach: The radius of the Voronoi cell, half the communication range.
        max_speed: The speed the velocity cannot exceed.
        gain: The fraction of the way to the centroid covered in a round.
        decrease: The factor of the step after an overshoot.
        increase: The factor of the step while the direction holds.
        min_gain: The smallest step, so that a device can always start again.
        dimensions: 2 to spread in the horizontal plane, keeping the height; 3 in space.

    Returns:
        The velocity, in the frame of the device.
    """
    spacing = voronoi_centroid(shape, position, offsets, reach, dimensions) * gain
    if shape(position) <= 0:
        control = spacing
    else:
        normal = shape.gradient(position, _GRADIENT_STEP)
        outward = (normal if dimensions == 3 else Vector(normal.x, normal.y)).normalize()
        aside = spacing - outward * max(0.0, spacing.dot(outward))
        control = -outward + aside.limit(_OUTSIDE_PUSH)
    return control.limit(max_speed) * _adaptive_step(control, decrease, increase, min_gain)

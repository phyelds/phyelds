"""
Shapes as signed distance functions (SDF): the distance from the border of a shape,
negative inside (``SDF.kt`` and its primitives).

Shapes compose with operators (``|`` union, ``&`` intersection, ``~`` complement, ``-``
difference) and transform (``expand``, ``ring``, ``translate``, ``rotate``, ``scale``),
keeping the distance exact where they can::

    ring = circle((0, 0), 10).ring(2)
    crescent = circle((0, 0), 10) - circle((0, 0), 10).translate(6, 0)
    cross = (segment((-5, -5), (5, 5)) | segment((-5, 5), (5, -5))).expand(1)

A shape built from planar coordinates is planar: in space it is a prism along the
vertical axis, so that drones at any height take it on. A ``circle``, ``segment`` or
``box`` built from coordinates in space is a sphere, a capsule or a box in space.
"""
from collections.abc import Callable, Sequence
import math

from phyelds.experimental.swarm.vector import Vector

Point = Sequence[float]


def _vector(position: Point) -> Vector:
    return position if isinstance(position, Vector) else Vector(*position)


def _planar(vector: Vector) -> Vector:
    return Vector(vector.x, vector.y)


class Shape:
    """
    A shape: called on a position, the signed distance from its border.

    Args:
        distance: The signed distance of a position, given as a ``Vector``.
    """

    def __init__(self, distance: Callable[[Vector], float]):
        self._distance = distance

    def __call__(self, position: Point) -> float:
        return self._distance(_vector(position))

    def inside(self, position: Point) -> bool:
        """Whether ``position`` is inside the shape or on its border."""
        return self(position) <= 0.0

    def __or__(self, other: "Shape") -> "Shape":
        return Shape(lambda position: min(self(position), other(position)))

    def __and__(self, other: "Shape") -> "Shape":
        return Shape(lambda position: max(self(position), other(position)))

    def __invert__(self) -> "Shape":
        return Shape(lambda position: -self(position))

    def __sub__(self, other: "Shape") -> "Shape":
        return self & ~other

    def expand(self, distance: float) -> "Shape":
        """The shape grown by ``distance``, rounding its corners; shrunk if negative."""
        return Shape(lambda position: self(position) - distance)

    def ring(self, thickness: float) -> "Shape":
        """
        The band of half-width ``thickness`` along the border.

        Raises:
            ValueError: If ``thickness`` is negative.
        """
        if thickness < 0:
            raise ValueError(f"the thickness of a ring cannot be negative, not {thickness}")
        return Shape(lambda position: abs(self(position)) - thickness)

    def translate(self, *offset: float) -> "Shape":
        """The shape moved by ``offset``, of two or three components."""
        shift = Vector(*offset)
        return Shape(lambda position: self(position - shift))

    def rotate(self, angle: float, pivot: Point = (0.0, 0.0)) -> "Shape":
        """
        The shape rotated counterclockwise by ``angle`` radians, around the vertical axis
        through ``pivot``.
        """
        center = Vector(*pivot)
        center = Vector(center.x, center.y)
        return Shape(lambda position: self(center + (position - center).rotate(-angle)))

    def scale(self, factor: float, pivot: Point = (0.0, 0.0, 0.0)) -> "Shape":
        """
        The shape scaled by ``factor`` around ``pivot``.

        Raises:
            ValueError: If ``factor`` is not positive.
        """
        if factor <= 0:
            raise ValueError(f"the factor of a scaling must be positive, not {factor}")
        center = Vector(*pivot)
        return Shape(lambda position: factor * self(center + (position - center) / factor))

    def gradient(self, position: Point, epsilon: float = 1e-3) -> Vector:
        """The gradient, by central differences of step ``epsilon``: it points outward."""
        here = _vector(position)
        components = []
        for axis in (Vector(epsilon, 0, 0), Vector(0, epsilon, 0), Vector(0, 0, epsilon)):
            change = self(here + axis) - self(here - axis)
            components.append(change / (2 * epsilon))
        return Vector(*components)

    def deepest_point_from(
        self, start: Point, epsilon: float = 1e-3, max_steps: int = 10_000
    ) -> Vector:
        """
        A point deep inside the shape, from ``start``: down to the border if outside, then
        inward while the distance from the border grows, halving the step down to
        ``epsilon``. It is a local maximum of the depth, so it lies inside the shape; the
        deepest point only for convex shapes.

        Args:
            start: Where to start from.
            epsilon: The step of the gradient, and the smallest step.
            max_steps: The most moves of each phase.

        Returns:
            The point found.
        """
        def inward(point: Vector, length: float) -> Vector:
            direction = self.gradient(point, epsilon).normalize()
            # Where the gradient vanishes, as at the center of a ring, any direction: +x.
            return point - (direction if direction != Vector() else Vector(-1, 0)) * length

        point = _vector(start)
        moves = 0
        while self(point) > 0.0 and moves < max_steps:
            point = inward(point, self(point) + epsilon)
            moves += 1
        step = max(-self(point), 1.0)
        moves = 0
        while step >= epsilon and moves < max_steps:
            candidate = inward(point, step)
            if self(candidate) < self(point):
                point = candidate
            else:
                step /= 2
            moves += 1
        return point


def _restricted(dimensions: int) -> Callable[[Vector], Vector]:
    """Keep the coordinates a shape built from points of ``dimensions`` coordinates uses."""
    return _planar if dimensions < 3 else (lambda vector: vector)


def circle(center: Point, radius: float) -> Shape:
    """
    A disk, or a sphere if ``center`` is in space.

    Raises:
        ValueError: If ``radius`` is not positive.
    """
    if radius <= 0:
        raise ValueError(f"the radius of a circle must be positive, not {radius}")
    keep, middle = _restricted(len(center)), Vector(*center)
    return Shape(lambda position: (keep(position) - middle).length() - radius)


def segment(start: Point, end: Point) -> Shape:
    """The segment from ``start`` to ``end``, of no width: ``expand`` it into a stroke."""
    keep, origin = _restricted(len(start)), Vector(*start)
    direction = Vector(*end) - origin
    squared_length = direction.dot(direction)

    def distance(position: Vector) -> float:
        to_point = keep(position) - origin
        if squared_length == 0:
            return to_point.length()
        along = min(max(to_point.dot(direction) / squared_length, 0.0), 1.0)
        return (to_point - direction * along).length()

    return Shape(distance)


def half_plane(start: Point, end: Point) -> Shape:
    """
    The half plane on the left of the line from ``start`` to ``end``.

    Raises:
        ValueError: If the two points are the same.
    """
    origin, direction = Vector(*start), Vector(*end) - Vector(*start)
    length = direction.length()
    if length == 0:
        raise ValueError(f"the two points of a half plane must differ, not {start} twice")
    return Shape(lambda position: -direction.cross(_planar(position) - origin).z / length)


def box(center: Point, size: Point, radius: float = 0.0) -> Shape:
    """
    A rectangle, or a box if ``center`` and ``size`` are in space, with corners rounded
    by ``radius``.

    Raises:
        ValueError: If a side is not positive, or ``radius`` is negative or longer than
            half a side.
    """
    if min(size) <= 0:
        raise ValueError(f"the sides of a box must be positive, not {size}")
    if not 0 <= radius <= min(size) / 2:
        raise ValueError(
            f"the radius of the corners must be between 0 and {min(size) / 2}, not {radius}"
        )
    keep, middle = _restricted(len(center)), Vector(*center)
    half = Vector(*size) / 2 - Vector(radius, radius, radius if len(size) > 2 else 0)

    def distance(position: Vector) -> float:
        offset = keep(position) - middle
        excess = Vector(abs(offset.x) - half.x, abs(offset.y) - half.y, abs(offset.z) - half.z)
        if len(size) < 3:
            excess = Vector(excess.x, excess.y, -math.inf)
        outside = Vector(max(excess.x, 0.0), max(excess.y, 0.0), max(excess.z, 0.0))
        return min(max(excess), 0.0) + outside.length() - radius

    return Shape(distance)


def rectangle(center: Point, width: float, height: float) -> Shape:
    """A rectangle ``width`` by ``height``."""
    return box(center, (width, height))


def rounded_rectangle(center: Point, width: float, height: float, radius: float) -> Shape:
    """A rectangle ``width`` by ``height``, with corners rounded by ``radius``."""
    return box(center, (width, height), radius)


def square(center: Point, side: float) -> Shape:
    """A square of the given ``side``."""
    return box(center, (side, side))


def polygon(vertices: Sequence[Point]) -> Shape:
    """
    The polygon with the given vertices, in order.

    Raises:
        ValueError: If there are fewer than three vertices.
    """
    if len(vertices) < 3:
        raise ValueError(f"a polygon needs at least three vertices, not {len(vertices)}")
    corners = [Vector(*vertex) for vertex in vertices]
    edges = list(zip([corners[-1]] + corners[:-1], corners))

    def distance(position: Vector) -> float:
        point = _planar(position)
        squared, inside = math.inf, False
        for previous, current in edges:
            edge, to_point = previous - current, point - current
            along = min(max(to_point.dot(edge) / edge.dot(edge), 0.0), 1.0)
            offset = to_point - edge * along
            squared = min(squared, offset.dot(offset))
            above_start, below_end = point.y >= current.y, point.y < previous.y
            left_of_edge = edge.cross(to_point).z > 0
            # The ray towards +x crosses the edge when all three hold, or none does.
            if above_start == below_end == left_of_edge:
                inside = not inside
        return -math.sqrt(squared) if inside else math.sqrt(squared)

    return Shape(distance)


def regular_polygon(center: Point, radius: float, sides: int, rotation: float = 0.0) -> Shape:
    """
    The regular polygon with ``sides`` vertices at ``radius`` from ``center``, the first
    at angle ``rotation``.

    Raises:
        ValueError: If ``radius`` is not positive or there are fewer than three sides.
    """
    if radius <= 0 or sides < 3:
        raise ValueError(
            f"a regular polygon needs a positive radius and three sides, not {radius}, {sides}"
        )
    middle = Vector(*center)
    return polygon([
        (middle + Vector(radius, 0).rotate(rotation + 2 * math.pi * index / sides)).position(2)
        for index in range(sides)
    ])


def hexagon(center: Point, radius: float) -> Shape:
    """The regular hexagon with its vertices at ``radius`` from ``center``."""
    return regular_polygon(center, radius, 6)


def star(center: Point, radius: float, points: int, spikiness: float | None = None) -> Shape:
    """
    A star with ``points`` tips at ``radius`` from ``center``, one pointing up.

    Args:
        center: The center.
        radius: The distance of the tips.
        points: How many tips.
        spikiness: From 2, a pentagon-like star, to ``points``, the spikiest; half the
            points if ``None``.

    Raises:
        ValueError: If the arguments do not make a star.
    """
    spikiness = points / 2 if spikiness is None else spikiness
    if radius <= 0 or points < 2 or not 2 <= spikiness <= points:
        raise ValueError(f"not a star: radius {radius}, {points} points, spikiness {spikiness}")
    middle, slice_angle = Vector(*center), math.pi / points
    tip = Vector(radius, 0)
    notch_length = (
        radius * math.sin(math.pi / spikiness - slice_angle) / math.sin(math.pi / spikiness)
    )
    notch = Vector(notch_length * math.cos(slice_angle), notch_length * math.sin(slice_angle))
    edge = segment(tip.position(2), notch.position(2))

    def distance(position: Vector) -> float:
        offset = _planar(position) - middle
        # Fold the point into the slice between a tip and the next notch, clockwise from +y.
        angle = math.atan2(offset.x, offset.y) % (2 * slice_angle)
        angle = min(angle, 2 * slice_angle - angle)
        folded = Vector(math.cos(angle), math.sin(angle)) * offset.length()
        inside = (notch - tip).cross(folded - tip).z > 0
        return -edge(folded) if inside else edge(folded)

    return Shape(distance)


def arc(center: Point, radius: float, start_angle: float, aperture: float) -> Shape:
    """
    The arc of ``radius`` around ``center``, from ``start_angle`` counterclockwise for
    ``aperture`` radians, of no width: ``expand`` it into a stroke.

    Raises:
        ValueError: If ``radius`` is negative or ``aperture`` is not in (0, 2π].
    """
    if radius < 0 or not 0 < aperture <= 2 * math.pi:
        raise ValueError(f"not an arc: radius {radius}, aperture {aperture}")
    middle = Vector(*center)
    first = middle + Vector(radius, 0).rotate(start_angle)
    last = middle + Vector(radius, 0).rotate(start_angle + aperture)

    def distance(position: Vector) -> float:
        point = _planar(position)
        offset = point - middle
        angle = (math.atan2(offset.y, offset.x) - start_angle) % (2 * math.pi)
        if angle <= aperture:
            return abs(radius - offset.length())
        return min((point - first).length(), (point - last).length())

    return Shape(distance)


def crescent(center: Point, radius: float, offset: float) -> Shape:
    """
    The disk of ``radius`` around ``center`` without the same disk moved right by
    ``offset``, exact: unlike their difference, it has no local minima outside, where
    robots would be trapped.

    Raises:
        ValueError: If ``radius`` is not positive or ``offset`` is not in (0, 2 radius).
    """
    if radius <= 0 or not 0 < offset < 2 * radius:
        raise ValueError(f"not a crescent: radius {radius}, offset {offset}")
    middle = Vector(*center)
    tip_x = offset / 2
    tip_y = math.sqrt(max(radius * radius - tip_x * tip_x, 0.0))

    def distance(position: Vector) -> float:
        point = _planar(position) - middle
        x, y = point.x, abs(point.y)
        if offset * (x * tip_y - y * tip_x) > offset * offset * max(tip_y - y, 0.0):
            return math.sqrt((x - tip_x) ** 2 + (y - tip_y) ** 2)
        inner = math.sqrt((x - offset) ** 2 + y * y)
        return max(math.sqrt(x * x + y * y) - radius, radius - inner)

    return Shape(distance)

"""
Vectors in space: velocities, headings and the offsets of the neighbors.

A ``Vector`` is three-dimensional; a planar swarm leaves ``z`` at zero, so that the same
blocks move robots on the ground and drones in the air.
"""
from collections.abc import Iterator
from dataclasses import dataclass
import math

from phyelds.data.codec import register


@register
@dataclass(frozen=True)
class Vector:
    """
    A vector in space, ``Vector()`` being zero; it travels in messages.

    Vectors add, subtract and scale with the usual operators. ``Vector(*position)`` is the
    vector of a position of two or three coordinates, and a vector unpacks into its three
    components, so that ``tuple(velocity)`` is what a simulator or a robot moves by.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def position(self, dimensions: int) -> tuple:
        """The first ``dimensions`` components, as a position of that many coordinates."""
        return tuple(self)[:dimensions]

    def __iter__(self) -> Iterator[float]:
        return iter((self.x, self.y, self.z))

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector") -> "Vector":
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> "Vector":
        return Vector(-self.x, -self.y, -self.z)

    def __mul__(self, factor: float) -> "Vector":
        return Vector(self.x * factor, self.y * factor, self.z * factor)

    __rmul__ = __mul__

    def __truediv__(self, divisor: float) -> "Vector":
        return Vector(self.x / divisor, self.y / divisor, self.z / divisor)

    def dot(self, other: "Vector") -> float:
        """The dot product."""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vector") -> "Vector":
        """The cross product."""
        return Vector(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        """The Euclidean length."""
        return math.sqrt(self.dot(self))

    def normalize(self) -> "Vector":
        """The vector of length one with the same direction; zero stays zero."""
        length = self.length()
        return self / length if length > 0 else Vector()

    def limit(self, maximum: float) -> "Vector":
        """The same vector, shortened to ``maximum`` if it is longer."""
        length = self.length()
        return self * (maximum / length) if length > maximum else self

    def rotate(self, angle: float) -> "Vector":
        """The vector rotated counterclockwise by ``angle`` radians around the vertical axis."""
        cos, sin = math.cos(angle), math.sin(angle)
        return Vector(self.x * cos - self.y * sin, self.x * sin + self.y * cos, self.z)

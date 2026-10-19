"""
Movement blocks: what a robot does on its own, or knowing where it is (MacroSwarm, §4.3).

Most need the ``position`` sensor: ``go_to``, ``is_close`` and ``explore`` read it, and
``neighbors_vectors`` shares it. The others combine with any block, for instance::

    wander = maintain_trajectory(brownian, period=5.0)
    velocity = (wander + avoid_obstacles(obstacles, 2.0)).normalize()
"""
from collections.abc import Callable, Iterable, Sequence
import math
import random

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.data import NeighborhoodField
from phyelds.experimental.swarm.vector import Vector
from phyelds.libraries.device import local_position
from phyelds.libraries.time import periodic_impulse


def _here() -> Vector:
    return Vector(*local_position())


@aggregate
def neighbors_vectors(position: Sequence[float] | None = None) -> NeighborhoodField[Vector]:
    """
    The vector from the device to each neighbor, zero to itself.

    Args:
        position: The position of the device; ``local_position()`` if ``None``. Only
            relative positions matter, so any frame shared by the neighbors works.

    Returns:
        The field of the vectors from the device to its neighbors.
    """
    here = _here() if position is None else Vector(*position)
    return neighbors(here).map(lambda there: there - here)


def stand_still() -> Vector:
    """Stay where you are: zero."""
    return Vector()


def brownian(scale: float = 1.0, *, dimensions: int = 2) -> Vector:
    """
    A random direction, uniform in the plane or in space, of length ``scale``.

    Args:
        scale: The length of the vector.
        dimensions: 2 for a direction in the horizontal plane, 3 for one in space.

    Returns:
        A new random vector at every call.
    """
    angle = random.uniform(0.0, 2 * math.pi)
    height = random.uniform(-1.0, 1.0) if dimensions == 3 else 0.0
    radius = math.sqrt(1.0 - height * height)
    return Vector(radius * math.cos(angle), radius * math.sin(angle), height) * scale


def go_to(target: Sequence[float], speed: float = 1.0) -> Vector:
    """
    Head to ``target`` at ``speed``; zero once on it.

    Args:
        target: The position to reach.
        speed: The length of the velocity.

    Returns:
        The velocity towards the target.
    """
    return (Vector(*target) - _here()).normalize() * speed


def is_close(target: Sequence[float], distance: float) -> bool:
    """Whether the device is within ``distance`` of ``target``."""
    return (Vector(*target) - _here()).length() <= distance


def _random_in(minimum: Sequence[float], maximum: Sequence[float]) -> tuple:
    return tuple(random.uniform(low, high) for low, high in zip(minimum, maximum))


@aggregate
def explore(
    minimum: Sequence[float],
    maximum: Sequence[float],
    speed: float = 1.0,
    *,
    tolerance: float | None = None,
) -> Vector:
    """
    Wander inside a box: head to a random goal in it, and draw a new one on reaching it.

    Args:
        minimum: The corner of the box with the lowest coordinates.
        maximum: The opposite corner.
        speed: The length of the velocity.
        tolerance: How close a goal counts as reached; ``speed`` if ``None``.

    Returns:
        The velocity towards the current goal.
    """
    set_goal, goal = remember(_random_in(minimum, maximum))
    if is_close(goal.value, speed if tolerance is None else tolerance):
        set_goal(_random_in(minimum, maximum))
    return go_to(goal.value, speed)


@aggregate
def maintain_trajectory(velocity: Callable[[], Vector], period: float) -> Vector:
    """
    Keep a velocity for ``period`` time units, then draw the next one.

    Args:
        velocity: What draws a velocity, such as ``brownian``. It runs in every round,
            so that the aggregate operations it calls stay aligned.
        period: How long each velocity lasts.

    Returns:
        The velocity drawn last.
    """
    drawn = velocity()
    set_kept, kept = remember(drawn)
    if periodic_impulse(period):
        set_kept(drawn)
    return kept.value


def maintain_until(velocity: Vector, condition: bool) -> Vector:
    """Keep ``velocity`` until ``condition`` holds, then stop."""
    return Vector() if condition else velocity


def avoid_obstacles(
    obstacles: Iterable[Vector], min_distance: float, norm: float = 100.0
) -> Vector:
    """
    Move away from the obstacles closer than ``min_distance``, the more the closer.

    Args:
        obstacles: The vector from the device to each obstacle it senses.
        min_distance: The distance below which an obstacle repels.
        norm: What the repulsion is divided by: each obstacle at distance ``d`` adds
            ``(min_distance - d) / norm`` away from it.

    Returns:
        The sum of the repulsions.
    """
    away = Vector()
    for obstacle in obstacles:
        distance = obstacle.length()
        if distance < min_distance:
            away = away - obstacle.normalize() * ((min_distance - distance) / norm)
    return away

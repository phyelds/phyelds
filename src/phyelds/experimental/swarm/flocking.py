"""
Flocking blocks: moving together, as Reynolds, Vicsek and Cucker-Smale (MacroSwarm, §4.4).

Each block takes the velocity of the device in the previous round, since flocking
iterates on velocities; remember it across rounds::

    velocity = remember_and_evolve(Vector(), lambda previous: vicsek(previous.value)).value

The neighbors a block looks at can be restricted, as the queries of MacroSwarm: to those
``within`` a distance, or to the ``nearest`` few. The device itself never counts as one,
but in ``vicsek``, which averages its velocity with theirs.
"""
from dataclasses import dataclass

from phyelds.calculus import aggregate, neighbors
from phyelds.experimental.swarm.movement import brownian, neighbors_vectors
from phyelds.experimental.swarm.vector import Vector


@dataclass(frozen=True)
class _Peer:
    """A neighbor: the vector to it, and the value it shares."""

    offset: Vector
    value: object


@aggregate
def _peers(value: object, within: float | None, nearest: int | None) -> list[_Peer]:
    """The neighbors of the device, closest first, with the ``value`` each shares."""
    values = neighbors(value)
    offsets = neighbors_vectors()
    peers = [
        _Peer(offset, values.data[node_id])
        for node_id, offset in offsets.exclude_self().items()
        if node_id in values.data and (within is None or offset.length() < within)
    ]
    peers.sort(key=lambda peer: peer.offset.length())
    return peers if nearest is None else peers[:nearest]


def _mean(vectors: list[Vector]) -> Vector:
    return sum(vectors, Vector()) / len(vectors) if vectors else Vector()


@aggregate
def separation(
    velocity: Vector, *, within: float | None = None, nearest: int | None = None
) -> Vector:
    """
    Steer away from the neighbors: the heading away from their mean, minus ``velocity``.

    Args:
        velocity: The velocity of the device in the previous round.
        within: Only the neighbors closer than this.
        nearest: Only this many neighbors, the closest.

    Returns:
        The steering; zero without neighbors.
    """
    peers = _peers(None, within, nearest)
    if not peers:
        return Vector()
    return _mean([-peer.offset for peer in peers]).normalize() - velocity


@aggregate
def alignment(
    velocity: Vector, *, within: float | None = None, nearest: int | None = None
) -> Vector:
    """
    Steer as the neighbors move: the heading of their mean velocity, minus ``velocity``.

    Args:
        velocity: The velocity of the device in the previous round, shared with them.
        within: Only the neighbors closer than this.
        nearest: Only this many neighbors, the closest.

    Returns:
        The steering; zero without neighbors.
    """
    peers = _peers(velocity, within, nearest)
    if not peers:
        return Vector()
    return _mean([peer.value for peer in peers]).normalize() - velocity


@aggregate
def cohesion(
    velocity: Vector, *, within: float | None = None, nearest: int | None = None
) -> Vector:
    """
    Steer towards the neighbors: the heading to their mean position, minus ``velocity``.

    Args:
        velocity: The velocity of the device in the previous round.
        within: Only the neighbors closer than this.
        nearest: Only this many neighbors, the closest.

    Returns:
        The steering; zero without neighbors.
    """
    peers = _peers(None, within, nearest)
    if not peers:
        return Vector()
    return _mean([peer.offset for peer in peers]).normalize() - velocity


@aggregate
def reynolds(  # pylint: disable=too-many-arguments
    velocity: Vector,
    *,
    vision: float | None = None,
    separation_within: float | None = None,
    separation_weight: float = 1.0,
    alignment_weight: float = 1.0,
    cohesion_weight: float = 1.0,
) -> Vector:
    """
    The boids of Reynolds: ``velocity`` plus the weighted headings of separation,
    alignment and cohesion.

    Args:
        velocity: The velocity of the device in the previous round.
        vision: The range of alignment and cohesion; all the neighbors if ``None``.
        separation_within: The range of separation, usually shorter; all the neighbors
            if ``None``.
        separation_weight: The weight of separation.
        alignment_weight: The weight of alignment.
        cohesion_weight: The weight of cohesion.

    Returns:
        The new velocity, not normalized.
    """
    return (
        velocity
        + separation(velocity, within=separation_within).normalize() * separation_weight
        + alignment(velocity, within=vision).normalize() * alignment_weight
        + cohesion(velocity, within=vision).normalize() * cohesion_weight
    )


@aggregate
def vicsek(
    velocity: Vector,
    *,
    alpha: float = 0.1,
    noise: float = 0.1,
    within: float | None = None,
    nearest: int | None = None,
) -> Vector:
    """
    The model of Vicsek: move towards the mean velocity of the neighbors and the device,
    with some noise.

    Args:
        velocity: The velocity of the device in the previous round, shared with them.
        alpha: How much of the mean replaces ``velocity``, from 0 to 1.
        noise: The length of the random vector added.
        within: Only the neighbors closer than this.
        nearest: Only this many neighbors, the closest.

    Returns:
        The new velocity.
    """
    peers = _peers(velocity, within, nearest)
    mean = _mean([velocity] + [peer.value for peer in peers])
    return velocity * (1 - alpha) + mean * alpha + brownian(noise)


@aggregate
def cucker_smale(
    velocity: Vector,
    strength: float,
    *,
    noise: float = 0.1,
    within: float | None = None,
    nearest: int | None = None,
) -> Vector:
    """
    The model of Cucker and Smale: move towards the velocity of each neighbor, the more
    the closer it is, with some noise.

    Args:
        velocity: The velocity of the device in the previous round, shared with them.
        strength: How much a neighbor at distance ``d`` pulls: ``strength / d``. The
            pulls of all the neighbors should add up to less than one, or the
            velocities overshoot each other and oscillate.
        noise: The length of the random vector added.
        within: Only the neighbors closer than this.
        nearest: Only this many neighbors, the closest.

    Returns:
        The new velocity.
    """
    pull = Vector()
    for peer in _peers(velocity, within, nearest):
        distance = peer.offset.length()
        if distance > 0:
            pull = pull + (peer.value - velocity) * (strength / distance)
    return velocity + brownian(noise) + pull

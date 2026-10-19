"""
Leader-based blocks: following a leader, and splitting the swarm in teams (MacroSwarm,
§4.5 and §4.6).

A leader is a Boolean field, true on the leaders: chosen in advance, sensed, or elected.
Each device follows the nearest leader, along the network.
"""
from collections.abc import Callable
from dataclasses import dataclass

from phyelds.calculus import aggregate, align, neighbors, remember
from phyelds.data import NeighborhoodField
from phyelds.data.codec import register
from phyelds.experimental.swarm.flocking import separation
from phyelds.experimental.swarm.movement import neighbors_vectors
from phyelds.experimental.swarm.vector import Vector
from phyelds.libraries.collect import collect_with
from phyelds.libraries.device import local_id
from phyelds.libraries.leader_election import elect_leaders

_UNREACHABLE = float("inf")


@aggregate
def _cast(
    source: bool,
    value: object,
    step: Callable[[object, Vector], object],
    offsets: NeighborhoodField[Vector],
) -> tuple[float, object]:
    """
    Spread ``value`` from the nearest source along the shortest paths, and the distance.

    Each device takes the value of the neighbor on its shortest path to the source, and
    ``step(value, offset)`` it, ``offset`` being the vector to that neighbor; away from any
    source, the distance is infinite and the value is ``value``.
    """
    set_entry, entry = remember((_UNREACHABLE, value))
    entries = neighbors(entry.value)
    best = (_UNREACHABLE, value)
    for node_id, (distance, there) in entries.exclude_self().items():
        offset = offsets.data.get(node_id)
        if offset is not None and distance + offset.length() < best[0]:
            best = (distance + offset.length(), step(there, offset))
    set_entry((0.0, value) if source else best)
    return entry.value


def _broadcast(source: bool, value: object) -> tuple[float, object]:
    """The value of the nearest source, and its distance, along the network."""
    return _cast(source, value, lambda there, _offset: there, neighbors_vectors())


@aggregate
def align_with_leader(leader: bool, velocity: Vector) -> Vector:
    """
    Move as the leader: its ``velocity``, spread to its area of influence.

    Args:
        leader: Whether the device is a leader.
        velocity: The velocity of the device; that of the leader is the one spread.

    Returns:
        The velocity of the nearest leader; ``velocity`` away from any.
    """
    return _broadcast(leader, velocity)[1]


@aggregate
def sink_at(leader: bool) -> Vector:
    """
    Head to the nearest leader: the direction of the shortest path to it, of length one.

    Args:
        leader: Whether the device is a leader.

    Returns:
        The heading to the leader; zero on the leader and away from any.
    """
    _, to_leader = _cast(
        leader, Vector(), lambda there, offset: there + offset, neighbors_vectors()
    )
    return to_leader.normalize()


@aggregate
def spin_around(center: bool) -> Vector:
    """
    Turn clockwise around the nearest center, seen from above.

    Args:
        center: Whether the device is a center.

    Returns:
        The heading perpendicular to that of ``sink_at``, of length one.
    """
    return sink_at(center).cross(Vector(0, 0, 1))


@aggregate
def is_team_formed(leader: bool, target_distance: float, necessary: int = 1) -> bool:
    """
    Whether every member of the team of the nearest leader has its closest ``necessary``
    neighbors within ``target_distance`` on average.

    Args:
        leader: Whether the device is a leader.
        target_distance: The mean distance to the closest neighbors that is close enough.
        necessary: How many neighbors count.

    Returns:
        What the leader gathered from its team; false until the leader is known.
    """
    offsets = neighbors_vectors()
    potential, _ = _broadcast(leader, None)
    closest = sorted(offset.length() for offset in offsets.exclude_self().values())[:necessary]
    close = len(closest) == necessary and sum(closest) / necessary <= target_distance
    gathered = collect_with(potential, close, lambda mine, theirs: mine and theirs)
    known, formed = _broadcast(leader, bool(gathered))
    return known < _UNREACHABLE and formed


@register
@dataclass(frozen=True)
class Team:
    """
    The team of a device: its ``leader``, whether it is ``formed``, and the ``velocity``
    that gathers it.
    """

    leader: int
    formed: bool
    velocity: Vector

    def inside(self, behaviour: Callable[[int], Vector]) -> Vector:
        """
        Run ``behaviour`` once the team is formed, apart from the other teams.

        Args:
            behaviour: Given the leader of the team, the velocity of the device; it runs
                aligned on the leader, so that its aggregate operations stay in the team.

        Returns:
            What ``behaviour`` returns; the velocity gathering the team until it is formed.
        """
        if not self.formed:
            return self.velocity
        with align(("team", self.leader)):
            return behaviour(self.leader)


def _no_condition(leader: bool) -> bool:  # pylint: disable=unused-argument
    return True


@aggregate
def team_formation(  # pylint: disable=too-many-arguments
    intra_distance: float,
    extra_distance: float,
    *,
    separation_weight: float = 1.0,
    condition: Callable[[bool], bool] = _no_condition,
    leader: bool | None = None,
) -> Team:
    """
    Split the swarm in teams: elect leaders, and gather each team around its leader until
    ``condition`` holds; from then on, the device stays in its team.

    Args:
        intra_distance: The distance the members keep from each other.
        extra_distance: The area of influence of a leader, where no other is elected.
        separation_weight: The weight of keeping apart, against gathering.
        condition: Given whether the device is a leader, whether its team is formed,
            such as ``lambda leader: is_team_formed(leader, 2.0)``.
        leader: Whether the device is a leader, to choose the leaders instead of
            electing them.

    Returns:
        The team of the device.
    """
    set_team, team = remember(Team(local_id(), False, Vector()))
    # The members of a formed team keep electing and relaying, so that the devices still
    # forming learn their leader through them.
    offsets = neighbors_vectors()
    is_leader = leader
    if leader is None:
        is_leader = elect_leaders(extra_distance, offsets.map(lambda offset: offset.length()))
    known, leader_id = _broadcast(is_leader, local_id())
    formed = condition(is_leader) and known < _UNREACHABLE
    spacing = separation(team.value.velocity, within=intra_distance) * separation_weight
    gather = sink_at(is_leader) + spacing
    if team.value.formed:
        set_team(Team(team.value.leader, True, Vector()))
    else:
        set_team(Team(leader_id, bool(formed), gather.normalize()))
    return team.value

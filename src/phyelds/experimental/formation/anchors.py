"""
Distance-based positioning (``AnchorElection.kt``, ``AnchorFrame.kt``,
``Localization.kt``): robots that sense only how far their neighbors are fix a frame on
three anchors, and trilaterate their positions in it.
"""
from dataclasses import dataclass
import math

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.data import NeighborhoodField, State
from phyelds.data.codec import register
from phyelds.experimental.formation.positioning import Frame
from phyelds.experimental.swarm.vector import Vector
from phyelds.libraries.collect import collect_with
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import candidacy, elect_leaders
from phyelds.libraries.spreading import broadcast, distance_to

_NONE, _ANCHOR_1, _ANCHOR_2, _ANCHOR_3 = range(4)
_NAN = float("nan")


def _plain(value):
    """The value held by a ``State``, or ``value`` itself."""
    return value.value if isinstance(value, State) else value


@register
@dataclass(frozen=True)
class _Candidate:
    """A robot that may become anchor 2 or 3: how far it is from the corners of the triangle."""

    node: int
    base_error: float
    top_error: float
    height: float


@register
@dataclass(frozen=True)
class _Reports:
    """What reaches anchor 1: the best candidates for the base and the top, and the anchors."""

    base: _Candidate | None
    top: _Candidate | None
    anchors: dict

    def merge(self, other: "_Reports") -> "_Reports":
        """Keep the best candidates of both, and all their anchors."""
        bases = [candidate for candidate in (self.base, other.base) if candidate is not None]
        tops = [candidate for candidate in (self.top, other.top) if candidate is not None]
        return _Reports(
            min(bases, key=lambda candidate: candidate.base_error, default=None),
            min(tops, key=lambda candidate: candidate.top_error, default=None),
            {**self.anchors, **other.anchors},
        )


@register
@dataclass(frozen=True)
class _AnchorChoice:
    """The anchors 2 and 3 that anchor 1 chose, and for how many rounds it missed them."""

    anchor2: int | None = None
    anchor3: int | None = None
    missed2: int = 0
    missed3: int = 0

    def update(self, reports: _Reports, min_height: float, patience: int) -> "_AnchorChoice":
        """
        Keep the anchors while their reports come, tolerating ``patience`` rounds without;
        otherwise pick the best base as anchor 2, then the best top as anchor 3.
        """
        reported2 = self.anchor2 is not None and self.anchor2 in reports.anchors
        missed2 = 0 if reported2 else self.missed2 + 1
        if self.anchor2 is None or missed2 > patience:
            return _AnchorChoice(anchor2=None if reports.base is None else reports.base.node)
        report3 = reports.anchors.get(self.anchor3)
        confirmed3 = report3 is not None and report3.height > min_height
        missed3 = 0 if confirmed3 else self.missed3 + 1
        if self.anchor3 is not None and missed3 <= patience:
            return _AnchorChoice(self.anchor2, self.anchor3, missed2, missed3)
        top = None if reports.top is None else reports.top.node
        return _AnchorChoice(self.anchor2, top, missed2, 0)


def _anchor3(base: float, to_anchor1: float, to_anchor2: float) -> Vector:
    """Where anchor 3 is, from its distances to anchors 1 and 2, ``base`` apart."""
    if not base > 0:
        return Vector(_NAN, _NAN)
    x = (to_anchor1 ** 2 - to_anchor2 ** 2 + base ** 2) / (2 * base)
    return Vector(x, math.sqrt(max(0.0, to_anchor1 ** 2 - x ** 2)))


def _trilaterate(base: float, anchor3: Vector, distances: tuple) -> Vector | None:
    """The position at ``distances`` from the anchors; ``None`` if unknown or collinear."""
    if not (base > 0 and anchor3.y > 0):
        return None
    to_anchor1, to_anchor2, to_anchor3 = distances
    x = (to_anchor1 ** 2 - to_anchor2 ** 2 + base ** 2) / (2 * base)
    y = to_anchor1 ** 2 - to_anchor3 ** 2 + anchor3.dot(anchor3) - 2 * anchor3.x * x
    y /= 2 * anchor3.y
    return Vector(x, y) if math.isfinite(x) and math.isfinite(y) else None


@aggregate
def _elect_anchors(  # pylint: disable=too-many-locals
    ranges: NeighborhoodField[float], bound: float, side: float, min_height: float, patience: int
) -> int:
    """The role of the robot: anchor 1, the leader, picks anchors 2 and 3 among all."""
    is_anchor1 = bool(elect_leaders(bound, strategy=candidacy(-local_id())))
    set_choice, previous = remember(_AnchorChoice())
    choice = previous.value if is_anchor1 else _AnchorChoice()
    chosen = _plain(broadcast(is_anchor1, choice if is_anchor1 else None, ranges))
    role = _NONE
    if is_anchor1:
        role = _ANCHOR_1
    elif chosen is not None and local_id() in (chosen.anchor2, chosen.anchor3):
        role = _ANCHOR_2 if local_id() == chosen.anchor2 else _ANCHOR_3
    is_anchor2 = role == _ANCHOR_2
    to_anchor1 = float(distance_to(is_anchor1, ranges))
    to_anchor2 = float(distance_to(is_anchor2, ranges))
    # Anchor 2 spreads its distance from anchor 1, the base of the triangle.
    base = float(broadcast(is_anchor2, to_anchor1 if is_anchor2 else _NAN, ranges))
    height = _anchor3(base, to_anchor1, to_anchor2).y
    height = height if math.isfinite(height) else 0.0
    base_error = abs(to_anchor1 - side)
    top_error = base_error + abs(to_anchor2 - side) if height > min_height else math.inf
    local = _Candidate(local_id(), base_error, top_error, height)
    candidate = local if not is_anchor1 and math.isfinite(base_error) else None
    top = None
    if candidate is not None and not is_anchor2 and math.isfinite(top_error):
        top = candidate
    anchors = {local_id(): local} if role in (_ANCHOR_2, _ANCHOR_3) else {}
    reports = _plain(collect_with(to_anchor1, _Reports(candidate, top, anchors), _Reports.merge))
    set_choice(choice.update(reports, min_height, patience) if is_anchor1 else choice)
    return role


@aggregate
def anchor_positioning(  # pylint: disable=too-many-arguments,too-many-locals
    ranges: NeighborhoodField[float] | None = None,
    *,
    side: float = 5.0,
    min_height: float = 3.0,
    patience: int = 10,
    bound: float = 200,
) -> Frame:
    """
    Distance-based positioning, for robots that sense only how far their neighbors are:
    three anchors fix the frame, the first at the origin, the second on the positive x
    axis and the third above it, and every robot trilaterates its position from its path
    distances to them. The anchors stay still. Planar: the robots fly at one height.

    Anchor 1 is the leader, the robot with the lowest id within ``bound`` hops; it picks
    anchors 2 and 3 among all the robots, as the corners of a triangle of sides about
    ``side`` along the paths, and replaces one only after missing it for ``patience``
    rounds, so that the frame does not move.

    Args:
        ranges: The distance to each neighbor; ``neighbors_distances()`` if ``None``.
        side: The side of the triangle of the anchors, small enough to fit in the shape.
        min_height: How far anchor 3 must be from the line of anchors 1 and 2, below
            the height of the triangle, so that the frame does not degenerate.
        patience: The rounds without a report of an anchor before it is replaced.
        bound: How many hops away anchor 1 leads.

    Returns:
        The frame of the robot; without a position until it knows the anchors. Its
        frame may be the mirror image of the world: steer with ``self_aligned``.
    """
    ranges = neighbors_distances() if ranges is None else ranges
    role = _elect_anchors(ranges, bound, side, min_height, patience)
    to_anchors = tuple(
        float(distance_to(role == anchor, ranges)) for anchor in (_ANCHOR_1, _ANCHOR_2, _ANCHOR_3)
    )
    is_anchor2, is_anchor3 = role == _ANCHOR_2, role == _ANCHOR_3
    base = float(broadcast(is_anchor2, to_anchors[0] if is_anchor2 else _NAN, ranges))
    anchor3_distances = to_anchors[:2] if is_anchor3 else (_NAN, _NAN)
    anchor3 = _anchor3(base, *_plain(broadcast(is_anchor3, anchor3_distances, ranges)))
    position = _trilaterate(base, anchor3, to_anchors)
    center = (Vector(base) + anchor3) / 3 if position is not None else Vector()
    return Frame(
        position,
        _offsets_from_estimates(position, ranges),
        center,
        is_leader=role == _ANCHOR_1,
        is_reference=role != _NONE,
        relative=True,
    )


@aggregate
def _offsets_from_estimates(
    position: Vector | None, ranges: NeighborhoodField[float]
) -> list[Vector]:
    """The vectors to the neighbors: their direction from the estimates, length from the ranges."""
    estimates = neighbors(position)
    offsets = []
    for node_id, there in estimates.exclude_self().items():
        measured = ranges.data.get(node_id)
        if position is None or there is None or measured is None:
            continue
        direction = there - position
        if direction.length() > 0 and math.isfinite(measured):
            offsets.append(direction * (measured / direction.length()))
    return offsets

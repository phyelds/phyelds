"""
Self-stabilizing leader election library with pluggable election strategies.
"""

from collections.abc import Callable
from dataclasses import dataclass
import math
import random
from typing import Any, Tuple

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import NeighborhoodField, StateT
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.utils import min_with_default

ElectionStrategy = Callable[[float, NeighborhoodField[float]], int | None]


@dataclass(frozen=True)
class Candidacy:
    """
    A candidate in a priority-based bounded leader election.

    Attributes:
        candidate: ID of the candidate device.
        distance: Accumulated distance from the candidate to the current device.
        strength: Priority of the candidate (larger values win; ties prefer shorter distance).
        hops: Ordered tuple of intermediate node IDs traversed from the candidate.
    """

    candidate: int
    distance: float
    strength: Any
    hops: tuple[int, ...] = ()

    def _sort_key(self) -> tuple[Any, float, int]:
        return (self.strength, -self.distance, -self.candidate)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Candidacy):
            return NotImplemented
        return self._sort_key() < other._sort_key()


def _validate_area(area: float) -> None:
    """Ensure ``area`` is finite and strictly positive so leader election can self-stabilize."""
    if isinstance(area, bool) or not math.isfinite(area) or area <= 0:
        raise ValueError(
            "area must be a finite positive number for self-stabilizing leader election, "
            f"got {area}"
        )


def _is_stale_candidacy(
    cand: Candidacy,
    new_dist: float,
    neighbor_candidacies: NeighborhoodField[Candidacy],
    distances: NeighborhoodField[float],
    peer_ids: set[int],
) -> bool:
    """Return True if an intermediate hop in ``peer_ids`` invalidates ``cand``."""
    for hop in cand.hops:
        if hop in peer_ids:
            hop_cand = neighbor_candidacies.data.get(hop)
            hop_edge = distances.data.get(hop)
            if hop_cand is None or hop_edge is None:
                return True
            if hop_cand.candidate != cand.candidate:
                return True
            if hop_cand.distance + hop_edge < new_dist:
                return True
    return False


def _select_best_candidacy(
    node_id: int,
    local_candidacy: Candidacy,
    area: float,
    neighbor_candidacies: NeighborhoodField[Candidacy],
    distances: NeighborhoodField[float],
) -> Candidacy:
    """Evaluate valid neighbor candidacies within ``area`` and return the winning ``Candidacy``."""
    peer_ids = {nid for nid in neighbor_candidacies.data if nid != node_id}
    best = local_candidacy
    for nid in sorted(peer_ids):
        cand = neighbor_candidacies.data.get(nid)
        edge = distances.data.get(nid)
        if cand is None or edge is None:
            continue
        if cand.candidate == node_id or node_id in cand.hops:
            continue
        new_dist = cand.distance + edge
        if new_dist > area:
            continue
        if _is_stale_candidacy(cand, new_dist, neighbor_candidacies, distances, peer_ids):
            continue
        extended = Candidacy(cand.candidate, new_dist, cand.strength, (*cand.hops, nid))
        best = max(best, extended)
    return best


@aggregate
def _candidacy_election_step(
    area: float,
    distances: NeighborhoodField[float],
    strength_value: Any,
) -> int:
    """Run one step of loop-free priority-based bounded leader election."""
    node_id = local_id()
    local_candidacy = Candidacy(node_id, 0.0, strength_value, ())
    set_field, neighbor_candidacies = exchange(local_candidacy)
    winner = _select_best_candidacy(
        node_id, local_candidacy, area, neighbor_candidacies, distances
    )
    set_field(winner)
    return winner.candidate


@aggregate
def _uuid_election_step(
    area: float,
    distances: NeighborhoodField[float],
) -> int | None:
    """Run one step of UUID-based symmetry-breaking leader election."""
    result: Tuple[StateT[float], int] = breaking_using_uids(random_uuid(), area, distances)
    if result[0] == float("inf"):
        return None
    return result[1]


def candidacy(strength: Any = None) -> ElectionStrategy:
    """
    Create a deterministic, priority-based bounded leader election strategy.

    Args:
        strength: Optional candidate priority (either a comparable value or a
            zero-argument callable returning one). Defaults to ``local_id()``.

    Returns:
        A pluggable ``ElectionStrategy``.
    """

    def strategy(area: float, distances: NeighborhoodField[float]) -> int:
        if strength is None:
            resolved_strength: Any = local_id()
        elif callable(strength):
            resolved_strength = strength()
        else:
            resolved_strength = strength
        return _candidacy_election_step(area, distances, resolved_strength)

    return strategy


def uuid_competition() -> ElectionStrategy:
    """Create the classic UUID symmetry-breaking leader election strategy (default)."""

    def strategy(area: float, distances: NeighborhoodField[float]) -> int | None:
        return _uuid_election_step(area, distances)

    return strategy


def _resolve_election_strategy(strategy: Any) -> ElectionStrategy:
    """Resolve ``None`` or an uncalled strategy factory into an ``ElectionStrategy``."""
    if strategy is None:
        return uuid_competition()
    if strategy in (uuid_competition, candidacy):
        return strategy()
    return strategy


@aggregate
def _run_elect_leader(
    area: float,
    distances: NeighborhoodField[float] | None,
    strategy: ElectionStrategy | None,
) -> int | None:
    """Aggregate implementation of elect_leader."""
    metric = hops_distance() if distances is None else distances
    active_strategy = _resolve_election_strategy(strategy)
    return active_strategy(area, metric)


def elect_leader(
    area: float,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: ElectionStrategy | None = None,
) -> int | None:
    """
    Elect a leader within ``area`` and return the elected leader's node ID.

    Args:
        area: Finite positive spatial bound of the election region.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional election strategy (``uuid_competition()`` or ``candidacy()``).

    Returns:
        The node ID of the leader for the current node's region (or ``None`` during transient).

    Raises:
        ValueError: If ``area`` is not a finite positive number.
    """
    _validate_area(area)
    return _run_elect_leader(float(area), distances, strategy)


@aggregate
def _run_elect_leaders(
    area: float,
    distances: NeighborhoodField[float] | None,
    strategy: ElectionStrategy | None,
) -> bool:
    """Aggregate implementation of elect_leaders."""
    leader_id = _run_elect_leader(area, distances, strategy)
    return leader_id == local_id()


def elect_leaders(
    area: float,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: ElectionStrategy | None = None,
) -> bool:
    """
    Elect leaders across the network and return True if the current node is a leader.

    Args:
        area: Finite positive spatial bound of the election region.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional election strategy (``uuid_competition()`` or ``candidacy()``).

    Returns:
        True if the current node is the elected leader of its region, False otherwise.

    Raises:
        ValueError: If ``area`` is not a finite positive number.
    """
    _validate_area(area)
    return _run_elect_leaders(float(area), distances, strategy)


@aggregate
def random_uuid() -> Tuple[StateT[float], int]:
    """
    Generate a random UUID for the node.
    :return: the random UUID
    """
    _, value = remember(random.random())
    return value, local_id()


@aggregate
def breaking_using_uids(
    uid: Tuple[StateT[float], int],
    area: float,
    distances: NeighborhoodField[float],
) -> StateT[tuple[float, int]]:
    """
    Break the symmetry using the UUID of the node.
    :param uid: the UUID of the node
    :param area: the area of the network
    :param distances: the distances to the neighbors
    :return: the current id of the leader
    """
    set_lead, lead = remember(uid)
    potential: float = distance_to(lead == uid, distances)
    new_lead: Tuple[float, int] = distance_competition(potential, area, uid, lead, distances)
    set_lead(new_lead)
    return lead


@aggregate
def distance_competition(
    current_distance: float,
    area: float,
    uid: Tuple[StateT[float], int],
    lead: StateT[Tuple[float, int]],
    distances: NeighborhoodField[float],
) -> StateT[Tuple[float, int]]:
    """
    Compare the distance of the current node with the distance of the neighbors.
    It leverages the fact that the tuple is a symmetric breaker.
    :param current_distance: current distance to the lead
    :param area: the maximum distance to the lead
    :param uid: the local id of the node
    :param lead: the current lead
    :param distances: the distances to the neighbors
    :return: the new lead
    """
    inf: Tuple[float, int] = (float("inf"), uid[1])
    neighbors_lead: NeighborhoodField[Tuple[float, int]] = neighbors(lead)
    condition: NeighborhoodField[bool] = (neighbors(current_distance) + distances) < (0.5 * area)
    lead_filtered: list[Tuple[float, int]] = neighbors_lead.select(condition)
    result: Tuple[float, int] = min_with_default(lead_filtered, uid)
    if current_distance > area:
        return uid
    if current_distance >= (0.5 * area):
        return inf
    return result

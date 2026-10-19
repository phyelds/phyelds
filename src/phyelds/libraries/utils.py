"""
This module contains utility functions and classes for various purposes.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import sys
from typing import Any, Generic, TypeVar

from phyelds.data import NeighborhoodField
from phyelds.data.codec import register

T = TypeVar("T")


def min_with_default(iterable: Any, default: Any = None) -> Any:
    """
    Returns the minimum value from an iterable, or a default value if the iterable is empty.
    :param iterable: a list of values (or any iterable)
    :param default: the default value to return if the iterable is empty
    :return: the minimum value from the iterable or the default value
    """
    if not iterable:
        return default
    if isinstance(iterable, dict):
        return min(iterable.values())
    if isinstance(iterable, (list, tuple, set, range)):
        return min(iterable)
    return default


def accumulate_distance(
    bottom: float,
    top: float,
    distance: float,
    edge_distance: float,
    accumulator: Callable[[float, float], float] = lambda a, b: a + b,
) -> float:
    """
    Combine two distances with bounds clamping and triangle-inequality validation.

    Args:
        bottom: Minimum allowed distance.
        top: Maximum allowed distance.
        distance: Current accumulated distance.
        edge_distance: Edge distance to add.
        accumulator: Function combining two distances.

    Returns:
        The clamped combined distance.

    Raises:
        ValueError: If the combined distance violates the triangle inequality.
    """
    raw_total = accumulator(distance, edge_distance)
    total = min(top, max(bottom, raw_total))
    if total < distance or total < edge_distance:
        raise ValueError(
            "Distance accumulation violates the triangle inequality: "
            f"accumulating {distance} and {edge_distance} produced {total}"
        )
    return total


@register
@dataclass(frozen=True)
class PathValue(Generic[T]):
    """
    Immutable value carried along a loop-free network path.

    Attributes:
        distance: Total accumulated distance from the path origin.
        data: Payload carried along the path.
        hops: Ordered tuple of node IDs traversed from origin to the sender.
    """

    distance: float
    data: T
    hops: tuple[int, ...] = ()

    @property
    def source(self) -> int | None:
        """Return the ID of the origin node, or ``None`` if no hops were taken."""
        return self.hops[0] if self.hops else None

    @property
    def next_hop(self) -> int | None:
        """Return the ID of the last hop toward the current node, or ``None`` if empty."""
        return self.hops[-1] if self.hops else None

    @property
    def length(self) -> int:
        """Return the number of hops in this path."""
        return len(self.hops)

    def __contains__(self, node_id: int) -> bool:
        return node_id in self.hops

    def extend(  # pylint: disable=too-many-arguments
        self,
        neighbor_id: int,
        edge_distance: float,
        accumulate_data: Callable[[float, float, T], T],
        *,
        bottom: float = 0.0,
        top: float = float("inf"),
        distance_accumulator: Callable[[float, float], float] = lambda a, b: a + b,
    ) -> "PathValue[T]":
        """
        Return a new ``PathValue`` extended through ``neighbor_id``.

        Args:
            neighbor_id: ID of the neighbor forwarding this path.
            edge_distance: Distance from ``neighbor_id`` to the current node.
            accumulate_data: Function ``(from_source, to_neighbor, data) -> new_data``.
            bottom: Minimum allowed distance.
            top: Maximum allowed distance.
            distance_accumulator: Function combining two distances.

        Returns:
            The extended ``PathValue``.
        """
        total_distance = accumulate_distance(
            bottom, top, self.distance, edge_distance, distance_accumulator
        )
        updated_data = accumulate_data(self.distance, edge_distance, self.data)
        return PathValue(total_distance, updated_data, (*self.hops, neighbor_id))

    def is_invalid_via_shortcut(
        self,
        accumulated_dist: float,
        neighbor_ids: set[int],
        neighbor_accumulated_distances: Mapping[int, float | None],
    ) -> bool:
        """Check whether an intermediate hop in the current neighborhood offers a shorter path."""
        for hop in self.hops:
            if hop in neighbor_ids:
                shortcut_dist = neighbor_accumulated_distances.get(hop)
                if shortcut_dist is None or shortcut_dist < accumulated_dist:
                    return True
        return False

    def all_common_hops_in_same_order(
        self,
        other: "PathValue[Any]",
        paths_hop_sets: Mapping[int | None, set[int]],
    ) -> bool:
        """Check that all hops shared between ``self`` and ``other`` appear in the same order."""
        other_hop_set = paths_hop_sets.get(other.next_hop, set())
        common_hops = [hop for hop in self.hops if hop in other_hop_set]
        if len(common_hops) <= 1:
            return True
        other_common = [hop for hop in other.hops if hop in set(common_hops)]
        return common_hops == other_common


def non_looping_paths(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    neighbor_data: NeighborhoodField[PathValue[T] | None],
    distances: NeighborhoodField[float],
    local_id: int,
    max_diameter: int = sys.maxsize,
    accumulate_data: Callable[[float, float, T], T] = lambda _s, _e, data: data,
    bottom: float = 0.0,
    top: float = float("inf"),
    distance_accumulator: Callable[[float, float], float] = lambda a, b: a + b,
) -> list[PathValue[T]]:
    """
    Build all valid, loop-free paths from neighbors, sorted by accumulated distance.

    Args:
        neighbor_data: Field of ``PathValue | None`` received from neighbors.
        distances: Field of edge distances to neighbors.
        local_id: ID of the current device.
        max_diameter: Maximum allowed hop count.
        accumulate_data: Function updating payload across an edge.
        bottom: Minimum distance bound.
        top: Maximum distance bound.
        distance_accumulator: Function combining two distances.

    Returns:
        List of extended ``PathValue`` instances sorted by total distance.
    """
    coerced = distances.coerce_in(bottom, top)
    peer_ids = {nid for nid in neighbor_data.data if nid != local_id}
    acc_distances: dict[int, float | None] = {}
    for nid in peer_ids:
        path = neighbor_data.data.get(nid)
        edge = coerced.data.get(nid)
        if path is not None and edge is not None:
            acc_distances[nid] = accumulate_distance(
                bottom, top, path.distance, edge, distance_accumulator
            )
        else:
            acc_distances[nid] = None

    candidates: list[PathValue[T]] = []
    for nid in sorted(peer_ids):
        path = neighbor_data.data.get(nid)
        edge = coerced.data.get(nid)
        acc_dist = acc_distances.get(nid)
        if path is None or edge is None or acc_dist is None:
            continue
        if path.length + 1 > max_diameter or local_id in path:
            continue
        if path.is_invalid_via_shortcut(acc_dist, peer_ids, acc_distances):
            continue
        candidates.append(
            path.extend(
                nid,
                edge,
                accumulate_data,
                bottom=bottom,
                top=top,
                distance_accumulator=distance_accumulator,
            )
        )

    candidates.sort(key=lambda candidate: (candidate.distance, candidate.length, candidate.hops))
    return candidates


def path_coherence(paths: Sequence[PathValue[T]]) -> list[PathValue[T]]:
    """
    Filter ``paths`` to retain only those that are mutually hop-order coherent.

    Args:
        paths: Sequence of loop-free ``PathValue`` candidates sorted by distance.

    Returns:
        Filtered list of path-coherent ``PathValue`` instances.
    """
    paths_hop_sets: dict[int | None, set[int]] = {
        path.next_hop: set(path.hops) for path in paths
    }
    coherent: list[PathValue[T]] = []
    for reference in paths:
        if reference.length <= 1 or all(
            other.length > reference.length
            or (other.length == reference.length and other.distance == reference.distance)
            or reference.all_common_hops_in_same_order(other, paths_hop_sets)
            for other in paths
        ):
            coherent.append(reference)
    return coherent

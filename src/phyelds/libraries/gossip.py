"""
Gossip library.

Provides network-wide gossip reductions (``gossip``, ``gossip_max``,
``gossip_min``, ``any_node``) with pluggable stabilization strategies
(``monotonic_gossip``, ``path_coherent_gossip``, ``time_replicated_gossip``).
"""

from collections.abc import Callable
import sys
from typing import Any, Dict, List, Set, TypeVar

from phyelds.calculus import aggregate, align, exchange, neighbors, remember
from phyelds.data import NeighborhoodField, StateT
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import cast_from
from phyelds.libraries.time import time_replicated
from phyelds.libraries.utils import PathValue, non_looping_paths, path_coherence

T = TypeVar("T")

GossipStrategy = Callable[[Any, Callable[..., Any]], Any]


def _reduce_pair(callback: Callable[..., T], first: T, second: T) -> T:
    """Apply ``callback`` (such as ``max``, ``min``, or a binary reducer) to two values."""
    return callback(first, second)


def _is_stale_through_neighbor(
    path: PathValue[T],
    neighbor_data: NeighborhoodField[PathValue[T] | None],
    peer_ids: set[int],
) -> bool:
    """Return True if any intermediate hop in ``peer_ids`` no longer advertises ``path.data``."""
    for hop in path.hops[:-1]:
        if hop in peer_ids:
            hop_path = neighbor_data.data.get(hop)
            if hop_path is None or hop_path.data != path.data:
                return True
    return False


def _select_best_path(
    local_candidate: PathValue[T],
    coherent_paths: list[PathValue[T]],
    callback: Callable[..., T],
) -> PathValue[T]:
    """Fold ``coherent_paths`` starting from ``local_candidate`` using ``callback``."""
    winner = local_candidate
    for candidate in coherent_paths:
        if winner.data == candidate.data:
            if candidate.length < winner.length:
                winner = candidate
            continue
        preferred = _reduce_pair(callback, winner.data, candidate.data)
        if preferred == winner.data:
            continue
        if preferred == candidate.data:
            winner = candidate
        else:
            winner = PathValue(
                max(winner.distance, candidate.distance),
                preferred,
                candidate.hops,
            )
    return winner


@aggregate
def _monotonic_gossip_step(value: T, callback: Callable[..., T]) -> StateT[T]:
    """Run a classic monotonic gossip step using ``remember`` and ``neighbors``."""
    set_gossip, gossip_value = remember(value)
    neighborhood_value: NeighborhoodField[T] = neighbors(gossip_value)
    new_value: T = callback(value, *neighborhood_value)
    set_gossip(new_value)
    return gossip_value


@aggregate
def _path_coherent_gossip_step(
    value: T,
    callback: Callable[..., T],
    max_diameter: int,
) -> T:
    """Run a self-stabilizing gossip step over loop-free coherent paths."""
    node_id = local_id()
    local_candidate: PathValue[T] = PathValue(0.0, value, ())
    set_field, neighbor_data = exchange(local_candidate)
    distances = hops_distance()
    candidates = non_looping_paths(neighbor_data, distances, node_id, max_diameter)
    peer_ids = {nid for nid in neighbor_data.data if nid != node_id}
    fresh_candidates = [
        path
        for path in candidates
        if not _is_stale_through_neighbor(path, neighbor_data, peer_ids)
    ]
    coherent = path_coherence(fresh_candidates)
    winner = _select_best_path(local_candidate, coherent, callback)
    set_field(winner)
    return winner.data


def monotonic_gossip() -> GossipStrategy:
    """Create the default non-stabilizing gossip strategy."""

    def strategy(value: Any, callback: Callable[..., Any]) -> Any:
        return _monotonic_gossip_step(value, callback)

    return strategy


def path_coherent_gossip(max_diameter: int = sys.maxsize) -> GossipStrategy:
    """
    Create a spatial self-stabilizing gossip strategy based on ``PathValue``.

    Args:
        max_diameter: Maximum hop count allowed for propagated paths.

    Returns:
        A pluggable ``GossipStrategy``.
    """

    def strategy(value: Any, callback: Callable[..., Any]) -> Any:
        return _path_coherent_gossip_step(value, callback, max_diameter)

    return strategy


def time_replicated_gossip(
    period: float,
    *,
    max_replicas: int = 2,
    clock: float | None = None,
) -> GossipStrategy:
    """
    Create a temporal self-stabilizing gossip strategy using overlapping time replicas.

    Args:
        period: Time interval between consecutive replica spawns.
        max_replicas: Number of concurrent replicas kept alive.
        clock: Optional local clock reading.

    Returns:
        A pluggable ``GossipStrategy``.
    """

    def strategy(value: Any, callback: Callable[..., Any]) -> Any:
        return time_replicated(
            lambda: _monotonic_gossip_step(value, callback),
            period=period,
            max_replicas=max_replicas,
            clock=clock,
        )

    return strategy


def _resolve_gossip_strategy(strategy: Any) -> GossipStrategy:
    """Resolve ``None`` or an uncalled strategy factory into a ``GossipStrategy``."""
    if strategy is None:
        return monotonic_gossip()
    if strategy in (monotonic_gossip, path_coherent_gossip):
        return strategy()
    return strategy


def _keyed_selector(
    selector: Callable[..., Any],
    key: Callable[[T], Any] | None,
) -> Callable[..., T]:
    """Build a multi-argument selector supporting an optional ``key`` function."""
    if key is None:
        return selector
    return lambda *values: selector(values, key=key)


@aggregate
def gossip(
    value: T,
    callback: Callable[..., T],
    *,
    strategy: GossipStrategy | None = None,
) -> StateT[T]:
    """
    Gossip ``value`` across the network using ``callback`` and an optional ``strategy``.

    Args:
        value: Local value contributed by the current device.
        callback: Reduction function combining values across neighbors.
        strategy: Optional gossip strategy (``monotonic_gossip()``,
            ``path_coherent_gossip()``, or ``time_replicated_gossip(...)``).

    Returns:
        The gossiped value.
    """
    active_strategy = _resolve_gossip_strategy(strategy)
    return active_strategy(value, callback)


@aggregate
def gossip_max(
    value: T,
    *,
    key: Callable[[T], Any] | None = None,
    strategy: GossipStrategy | None = None,
) -> StateT[T]:
    """
    Gossip the maximum value across the network.

    Args:
        value: Local value to compare.
        key: Optional key function extracting a comparison key from each value.
        strategy: Optional gossip strategy.

    Returns:
        The maximum value across the network.
    """
    return gossip(value, _keyed_selector(max, key), strategy=strategy)


@aggregate
def gossip_min(
    value: T,
    *,
    key: Callable[[T], Any] | None = None,
    strategy: GossipStrategy | None = None,
) -> StateT[T]:
    """
    Gossip the minimum value across the network.

    Args:
        value: Local value to compare.
        key: Optional key function extracting a comparison key from each value.
        strategy: Optional gossip strategy.

    Returns:
        The minimum value across the network.
    """
    return gossip(value, _keyed_selector(min, key), strategy=strategy)


@aggregate
def any_node(
    condition: bool,
    *,
    strategy: GossipStrategy | None = None,
) -> StateT[bool]:
    """
    Check whether ``condition`` holds on at least one device in the network.

    With the default ``monotonic_gossip()`` strategy, this behaves like ``ever_happened``
    (once True on any node, it remains True). With ``path_coherent_gossip()`` or
    ``time_replicated_gossip(...)``, it self-stabilizes to reflect whether ``condition``
    is currently True on any active node.

    Args:
        condition: Local boolean condition on the current device.
        strategy: Optional gossip strategy.

    Returns:
        True if ``condition`` is satisfied according to ``strategy``.
    """
    return gossip_max(bool(condition), strategy=strategy)


@aggregate
def gossip_mean(value: float) -> float:
    """
    Smooth and diffuse ``value`` across the network by neighborhood averaging.

    At each round, averages the current local ``value`` with the estimates received
    from neighbors, remaining self-stabilizing when input values change.

    Args:
        value: Local numeric value.

    Returns:
        The locally averaged estimate.
    """
    set_estimate, neighbor_estimates = exchange(float(value))
    peer_sum = float(neighbor_estimates.sum(include_self=False))
    avg = (float(value) + peer_sum) / len(neighbor_estimates.data)
    set_estimate(avg)
    return avg


@aggregate
def stabilizing_gossip(
    value: T,
    max_diameter: int,
    callback: Callable[..., T],
) -> StateT[T]:
    """
    Gossip a value in the network using a callable function to choose the value to gossip.
    This function will stabilize the gossip value by applying the callback function until
    no changes are made.
    :param value: The value to gossip.
    :param max_diameter: The maximum diameter to consider for gossiping.
    :param callback: The callback function to apply on the value.
    :return: The stabilized gossiped value.
    """
    all_ids: Set[int] = gossip({local_id()}, set.union)
    all_data: Dict[int, Any] = {}
    for node_id in all_ids:
        with align(node_id):
            all_data[node_id] = cast_from(
                local_id() == node_id,
                (value, 0),
                lambda x: (x[0], x[1] + 1),
                hops_distance(),
            )
    filtered_data: Dict[int, Any] = {
        k: v for k, v in all_data.items() if v[1] <= max_diameter
    }
    filtered_values: List[T] = [v[0] for v in filtered_data.values()]
    return callback(value, *filtered_values)

"""
Diffusion (information) library for phyelds.

Provides high-level spreading primitives (``distance_to``, ``cast_from``,
``broadcast``) parameterized by pluggable propagation strategies
(``bellman_ford``, ``path_coherent``).
"""

from collections.abc import Callable
from dataclasses import dataclass
import inspect
import math
import sys
from typing import Any, TypeVar

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import NeighborhoodField, StateT
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.utils import (
    PathValue,
    accumulate_distance,
    min_with_default,
    non_looping_paths,
    path_coherence,
)

T = TypeVar("T")

AccumulateStep = Callable[[float, float, Any], Any]
SpreadingStrategy = Callable[[bool, Any, AccumulateStep, NeighborhoodField[float]], Any]


@dataclass(frozen=True)
class _MetricBounds:
    """Configuration for distance bounds and accumulation."""

    bottom: float = 0.0
    top: float = float("inf")
    distance_accumulator: Callable[[float, float], float] = lambda a, b: a + b


def _normalize_accumulation(accumulation: Callable[..., T]) -> Callable[[float, float, T], T]:
    """Adapt a 1-, 2-, or 3-argument accumulation callable to ``(from_source, edge, data)``."""
    try:
        params = list(inspect.signature(accumulation).parameters.values())
    except (TypeError, ValueError):
        return lambda _from_source, _edge, data: accumulation(data)

    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        return accumulation

    positional = [
        p
        for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) == 1:
        return lambda _from_source, _edge, data: accumulation(data)
    if len(positional) == 2:
        return lambda _from_source, edge, data: accumulation(edge, data)
    return accumulation


def _best_bellman_ford_neighbor(
    neighbor_entries: NeighborhoodField[tuple[float, T]],
    distances: NeighborhoodField[float],
    data: T,
    accumulate_step: Callable[[float, float, T], T],
    bounds: _MetricBounds,
) -> tuple[float, T]:
    """Select the shortest path offered by neighbors under Bellman-Ford."""
    coerced = distances.coerce_in(bounds.bottom, bounds.top)
    best_dist = bounds.top
    best_val = data
    for nid, (from_source, neighbor_val) in neighbor_entries.exclude_self().items():
        edge = coerced.data.get(nid)
        if edge is None or from_source >= bounds.top:
            continue
        total_dist = accumulate_distance(
            bounds.bottom, bounds.top, from_source, edge, bounds.distance_accumulator
        )
        if total_dist < best_dist:
            best_dist = total_dist
            best_val = accumulate_step(from_source, edge, neighbor_val)
    return best_dist, best_val


@aggregate
def _bellman_ford_cast(
    source: bool,
    data: T,
    accumulate_step: Callable[[float, float, T], T],
    distances: NeighborhoodField[float],
    bounds: _MetricBounds,
) -> StateT[T]:
    """Run a single Bellman-Ford gradient cast step."""
    top_entry: tuple[float, T] = (bounds.top, data)
    set_state, current_state = remember(top_entry)
    neighbor_entries: NeighborhoodField[tuple[float, T]] = neighbors(current_state)
    best_peer = _best_bellman_ford_neighbor(
        neighbor_entries, distances, data, accumulate_step, bounds
    )
    next_entry: tuple[float, T] = (bounds.bottom, data) if source else best_peer
    set_state(next_entry)
    return current_state[1]


def _select_anisotropic_paths(
    node_id: int,
    local_candidate: PathValue[T] | None,
    data: T,
    candidates: list[PathValue[T]],
    neighbor_ids: set[int],
) -> tuple[NeighborhoodField[PathValue[T] | None], T]:
    """Build the outgoing anisotropic field and select the local result for path_coherent."""
    best_paths: list[PathValue[T]] = (
        [local_candidate] if local_candidate is not None else path_coherence(candidates)
    )
    default_path: PathValue[T] | None = best_paths[0] if best_paths else None
    outgoing: dict[int, PathValue[T] | None] = {}
    for nid in neighbor_ids:
        if nid == node_id:
            outgoing[nid] = default_path
        else:
            outgoing[nid] = next(
                (path for path in best_paths if path.next_hop != nid),
                None,
            )
    result: T = default_path.data if default_path is not None else data
    return NeighborhoodField(outgoing, node_id, default=default_path), result


@aggregate
def _path_coherent_cast(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    source: bool,
    data: T,
    accumulate_step: Callable[[float, float, T], T],
    distances: NeighborhoodField[float],
    max_diameter: int,
    bounds: _MetricBounds,
) -> T:
    """Run a fast self-healing gradient cast step using loop-free coherent paths."""
    node_id = local_id()
    local_candidate: PathValue[T] | None = (
        PathValue(bounds.bottom, data, ()) if source else None
    )
    init_field: NeighborhoodField[PathValue[T] | None] = NeighborhoodField(
        {node_id: local_candidate}, node_id, default=local_candidate
    )
    set_field, neighbor_data = exchange(init_field)
    candidates = non_looping_paths(
        neighbor_data=neighbor_data,
        distances=distances,
        local_id=node_id,
        max_diameter=max_diameter,
        accumulate_data=accumulate_step,
        bottom=bounds.bottom,
        top=bounds.top,
        distance_accumulator=bounds.distance_accumulator,
    )
    outgoing_field, result = _select_anisotropic_paths(
        node_id, local_candidate, data, candidates, set(distances.data.keys())
    )
    set_field(outgoing_field)
    return result


def bellman_ford(
    *,
    bottom: float = 0.0,
    top: float = float("inf"),
    distance_accumulator: Callable[[float, float], float] = lambda a, b: a + b,
) -> SpreadingStrategy:
    """
    Create a Bellman-Ford spreading strategy.

    Args:
        bottom: Zero-distance value at a source.
        top: Maximum distance bound.
        distance_accumulator: Function combining two distances.

    Returns:
        A pluggable ``SpreadingStrategy``.
    """
    bounds = _MetricBounds(bottom, top, distance_accumulator)

    def strategy(
        source: bool,
        data: Any,
        accumulate_step: AccumulateStep,
        distances: NeighborhoodField[float],
    ) -> Any:
        return _bellman_ford_cast(source, data, accumulate_step, distances, bounds)

    return strategy


def path_coherent(
    max_diameter: int = sys.maxsize,
    *,
    bottom: float = 0.0,
    top: float = float("inf"),
    distance_accumulator: Callable[[float, float], float] = lambda a, b: a + b,
) -> SpreadingStrategy:
    """
    Create a fast self-healing spreading strategy based on coherent loop-free paths.

    Args:
        max_diameter: Maximum number of hops allowed along any path.
        bottom: Zero-distance value at a source.
        top: Maximum distance bound.
        distance_accumulator: Function combining two distances.

    Returns:
        A pluggable ``SpreadingStrategy`` immune to the rising-value problem.
    """
    bounds = _MetricBounds(bottom, top, distance_accumulator)

    def strategy(
        source: bool,
        data: Any,
        accumulate_step: AccumulateStep,
        distances: NeighborhoodField[float],
    ) -> Any:
        return _path_coherent_cast(
            source, data, accumulate_step, distances, max_diameter, bounds
        )

    return strategy


def _resolve_strategy(strategy: Any) -> SpreadingStrategy:
    """Resolve ``None`` or an uncalled strategy factory into a ``SpreadingStrategy``."""
    if strategy is None:
        return bellman_ford()
    if strategy in (bellman_ford, path_coherent):
        return strategy()
    return strategy


@aggregate
def distance_to(
    source: bool,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: SpreadingStrategy | None = None,
) -> StateT[float]:
    """
    Calculate the distance to the nearest source node in the network.

    Args:
        source: True if the current node is a source.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional spreading strategy (e.g. ``path_coherent()``). When omitted,
            uses classic Bellman-Ford propagation.

    Returns:
        The estimated distance to the nearest source.
    """
    metric = hops_distance() if distances is None else distances
    if strategy is None:
        set_gradient, gradient = remember(float("inf"))
        neighbors_gradients: NeighborhoodField[float] = neighbors(gradient) + metric
        set_gradient(
            0.0
            if source
            else min_with_default(neighbors_gradients.exclude_self(), float("inf"))
        )
        return gradient

    active_strategy = _resolve_strategy(strategy)
    fallback = 0.0 if source else float("inf")
    return active_strategy(
        source,
        fallback,
        lambda from_source, edge, _data: from_source + edge,
        metric,
    )


@aggregate
def cast_from(
    source: bool,
    data: T,
    accumulation: Callable[..., T],
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: SpreadingStrategy | None = None,
) -> StateT[T]:
    """
    Propagate and transform ``data`` from the nearest ``source`` node along a gradient.

    Args:
        source: True if the current node is a source.
        data: Value produced at a source (and fallback when no source is reachable).
        accumulation: Transformation applied at each hop. May accept ``(neighbor_data)``,
            ``(edge_distance, neighbor_data)``, or ``(from_source, edge_distance, neighbor_data)``.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional spreading strategy (``bellman_ford()`` or ``path_coherent()``).

    Returns:
        The propagated and accumulated value at the current node.
    """
    metric = hops_distance() if distances is None else distances
    step_fn = _normalize_accumulation(accumulation)
    active_strategy = _resolve_strategy(strategy)
    return active_strategy(source, data, step_fn, metric)


@aggregate
def broadcast(
    source: bool,
    data: T,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: SpreadingStrategy | None = None,
) -> StateT[T]:
    """
    Broadcast ``data`` from the nearest ``source`` node across the network.

    Args:
        source: True if the current node is a source.
        data: Value to broadcast from the source (and fallback when unreachable).
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional spreading strategy (``bellman_ford()`` or ``path_coherent()``).

    Returns:
        The value broadcast from the nearest source.
    """
    return cast_from(source, data, lambda x: x, distances, strategy=strategy)


@aggregate
def distance_between(
    source: bool,
    target: bool,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: SpreadingStrategy | None = None,
) -> StateT[float]:
    """
    Compute the distance between ``source`` and ``target`` and broadcast it across the network.

    Args:
        source: True on source devices.
        target: True on target devices.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional spreading strategy (``bellman_ford()`` or ``path_coherent()``).

    Returns:
        The distance between the nearest ``source`` and ``target``.
    """
    metric = hops_distance() if distances is None else distances
    dist_to_target = distance_to(target, metric, strategy=strategy)
    return broadcast(source, dist_to_target, metric, strategy=strategy)


@aggregate
def _run_channel(
    source: bool,
    target: bool,
    width: float,
    distances: NeighborhoodField[float] | None,
    strategy: SpreadingStrategy | None,
) -> bool:
    """Aggregate implementation of channel."""
    metric = hops_distance() if distances is None else distances
    dist_source = float(distance_to(source, metric, strategy=strategy))
    dist_target = float(distance_to(target, metric, strategy=strategy))
    dist_between = float(distance_between(source, target, metric, strategy=strategy))
    total = dist_source + dist_target
    return (
        math.isfinite(total)
        and math.isfinite(dist_between)
        and total <= dist_between + width + 1e-12
    )


def channel(
    source: bool,
    target: bool,
    width: float = 0.0,
    distances: NeighborhoodField[float] | None = None,
    *,
    strategy: SpreadingStrategy | None = None,
) -> bool:
    """
    Select the devices on a near-shortest route from ``source`` to ``target``.

    A device belongs to the channel when the shortest route from ``source`` to ``target``
    through it is at most ``width`` longer than the shortest route overall.

    Args:
        source: True on source devices.
        target: True on target devices.
        width: Non-negative slack around the shortest path length.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        strategy: Optional spreading strategy (``bellman_ford()`` or ``path_coherent()``).

    Returns:
        True if the current device belongs to the channel between ``source`` and ``target``.

    Raises:
        ValueError: If ``width < 0`` or is NaN.
    """
    if math.isnan(width) or width < 0:
        raise ValueError(f"width must be non-negative, got {width}")
    return _run_channel(source, target, float(width), distances, strategy)

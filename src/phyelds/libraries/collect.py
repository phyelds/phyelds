"""
Collect library.

Functions used to collect and aggregate information from the network toward
source nodes along a potential gradient, with pluggable collection strategies.
"""

from collections.abc import Callable
from typing import Any, Optional, Tuple, TypeVar, Union

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import NeighborhoodField, StateT
from phyelds.data.codec import register
from phyelds.libraries.device import local_id
from phyelds.libraries.spreading import SpreadingStrategy, broadcast, distance_to

T = TypeVar("T")

CollectStrategy = Callable[[StateT[float], Any, Callable[[Any, Any], Any]], Any]

_NO_DATA = register(object(), "collect.no_data")


@aggregate
def find_parent(potential: StateT[float]) -> Optional[int]:
    """
    Find the neighbor to send data to along a ``potential`` field.

    Args:
        potential: Local potential value (such as a distance) at the current node.

    Returns:
        The ID of the neighbor with the lowest potential, or ``None`` if no neighbor
            has a potential lower than ``potential``.
    """
    neighbors_potential: NeighborhoodField[float] = neighbors(potential)
    min_value: Tuple[int, float] = min(neighbors_potential.data.items(), key=lambda x: x[1])
    if min_value[1] >= potential:
        return None
    return min_value[0]


@aggregate
def find_parents(
    potential: StateT[float],
    predicate: Callable[[int, float], bool] | None = None,
) -> set[int]:
    """
    Find all parent neighbor IDs along a ``potential`` field.

    Args:
        potential: Local potential value at the current node.
        predicate: Optional filter ``(neighbor_id, neighbor_potential) -> bool``.
            Defaults to selecting neighbors with potential strictly less than ``potential``.

    Returns:
        Set of neighbor IDs that act as parents of the current device.
    """
    neighbors_potential: NeighborhoodField[float] = neighbors(potential)
    check = (lambda _nid, val: val < potential) if predicate is None else predicate
    return {
        nid
        for nid, val in neighbors_potential.exclude_self().items()
        if check(nid, val)
    }


@aggregate
def _broadcast_collect(
    potential: StateT[float],
    local: T,
    accumulation: Callable[[T, T], T],
) -> StateT[T]:
    """Collect values up the potential gradient using broadcast neighbor fields."""
    set_collections, collections = remember(local)
    n_collections: NeighborhoodField[T] = neighbors(collections)
    parents: NeighborhoodField[Optional[int]] = neighbors(find_parent(potential))
    operations: T = local
    for parent, value in zip(parents, n_collections):
        if local_id() == parent:
            operations = accumulation(operations, value)
    set_collections(operations)
    return collections


@aggregate
def _point_to_point_collect(
    potential: StateT[float],
    local: T,
    accumulation: Callable[[T, T], T],
) -> T:
    """Collect values up the potential gradient using anisotropic exchange."""
    node_id = local_id()
    parent = find_parent(potential)
    init_field: NeighborhoodField[Any] = NeighborhoodField({}, node_id, default=_NO_DATA)
    set_field, incoming = exchange(init_field)

    accumulated: T = local
    for value in incoming.exclude_self().values():
        if value is not _NO_DATA:
            accumulated = accumulation(accumulated, value)

    outgoing_data = {parent: accumulated} if parent is not None else {}
    set_field(NeighborhoodField(outgoing_data, node_id, default=_NO_DATA))
    return accumulated


def broadcast_collect() -> CollectStrategy:
    """Create a broadcast-based collection strategy (default, uses ``remember`` + ``neighbors``)."""

    def strategy(
        potential: StateT[float],
        local: Any,
        accumulation: Callable[[Any, Any], Any],
    ) -> Any:
        return _broadcast_collect(potential, local, accumulation)

    return strategy


def point_to_point() -> CollectStrategy:
    """Create an anisotropic ``exchange``-based collection strategy (sends data only to parent)."""

    def strategy(
        potential: StateT[float],
        local: Any,
        accumulation: Callable[[Any, Any], Any],
    ) -> Any:
        return _point_to_point_collect(potential, local, accumulation)

    return strategy


@aggregate
def _multi_path_collect(
    potential: StateT[float],
    local: T,
    accumulation: Callable[[T, T], T],
    divide: Callable[[T, int], T],
) -> T:
    """Collect values up a DAG by splitting each node's total equally among all parents."""
    node_id = local_id()
    parents = find_parents(potential)
    init_field: NeighborhoodField[Any] = NeighborhoodField({}, node_id, default=_NO_DATA)
    set_field, incoming = exchange(init_field)

    accumulated: T = local
    for value in incoming.exclude_self().values():
        if value is not _NO_DATA:
            accumulated = accumulation(accumulated, value)

    if parents:
        share = divide(accumulated, len(parents))
        outgoing_data = {pid: share for pid in parents}
    else:
        outgoing_data = {}
    set_field(NeighborhoodField(outgoing_data, node_id, default=_NO_DATA))
    return accumulated


def multi_path(
    divide: Callable[[Any, int], Any] = lambda val, count: val / count,
) -> CollectStrategy:
    """
    Create a multi-path DAG collection strategy (FCPP ``mp_collection``).

    Each node divides its accumulated value across all neighbors with lower
    potential using ``divide(value, num_parents)``.

    Args:
        divide: Function splitting a value across ``count`` parents.

    Returns:
        A pluggable ``CollectStrategy``.
    """

    def strategy(
        potential: StateT[float],
        local: Any,
        accumulation: Callable[[Any, Any], Any],
    ) -> Any:
        return _multi_path_collect(potential, local, accumulation, divide)

    return strategy


def _resolve_collect_strategy(strategy: Any) -> CollectStrategy:
    """Resolve ``None`` or an uncalled strategy factory into a ``CollectStrategy``."""
    if strategy is None:
        return broadcast_collect()
    if strategy in (broadcast_collect, point_to_point, multi_path):
        return strategy()
    return strategy


@aggregate
def collect_with(
    potential: StateT[float],
    local: T,
    accumulation: Callable[[T, T], T],
    *,
    strategy: CollectStrategy | None = None,
) -> StateT[T]:
    """
    Accumulate ``local`` values from children to parents along ``potential``.

    Args:
        potential: Potential value used to determine parent-child relationships.
        local: Local value to start with at each node.
        accumulation: Binary function combining two values (e.g. sum, max, union).
        strategy: Optional collection strategy (``broadcast_collect()`` or ``point_to_point()``).

    Returns:
        The accumulated value at the current node.
    """
    active_strategy = _resolve_collect_strategy(strategy)
    return active_strategy(potential, local, accumulation)


@aggregate
def count_nodes(
    potential: StateT[float],
    *,
    strategy: CollectStrategy | None = None,
) -> StateT[int]:
    """
    Count the number of nodes in the sub-tree defined by ``potential``.

    Args:
        potential: The potential field.
        strategy: Optional collection strategy.

    Returns:
        The count of nodes in the sub-tree rooted at the current device.
    """
    return collect_with(potential, 1, lambda x, y: x + y, strategy=strategy)


@aggregate
def sum_values(
    potential: StateT[float],
    local: Union[int, float],
    *,
    strategy: CollectStrategy | None = None,
) -> StateT[Union[int, float]]:
    """
    Sum numeric values up the ``potential`` gradient.

    Args:
        potential: The potential field.
        local: The local numeric value.
        strategy: Optional collection strategy.

    Returns:
        The sum of values in the sub-tree rooted at the current device.
    """
    return collect_with(potential, local, lambda x, y: x + y, strategy=strategy)


@aggregate
def mean_values(
    potential: StateT[float],
    local: Union[int, float],
    *,
    strategy: CollectStrategy | None = None,
) -> float:
    """
    Compute the arithmetic mean of ``local`` values across the sub-tree defined by ``potential``.

    Args:
        potential: The potential field.
        local: The local numeric value.
        strategy: Optional collection strategy.

    Returns:
        The mean of values in the sub-tree rooted at the current device.
    """
    total = sum_values(potential, float(local), strategy=strategy)
    count = count_nodes(potential, strategy=strategy)
    return float(total) / float(count)


@aggregate
def collect_or(
    potential: float,
    local: bool,
    *,
    strategy: CollectStrategy | None = None,
) -> StateT[bool]:
    """
    Perform a logical OR collection up the ``potential`` gradient.

    Args:
        potential: The potential field.
        local: The local boolean condition.
        strategy: Optional collection strategy.

    Returns:
        True if any node in the sub-tree satisfies ``local``.
    """
    return collect_with(potential, local, lambda x, y: x or y, strategy=strategy)


@aggregate
def summarize(  # pylint: disable=too-many-arguments
    sink: bool,
    local: T,
    accumulation: Callable[[T, T], T],
    distances: NeighborhoodField[float] | None = None,
    *,
    spreading_strategy: SpreadingStrategy | None = None,
    collect_strategy: CollectStrategy | None = None,
) -> StateT[T]:
    """
    Collect ``local`` values into ``sink`` and broadcast the aggregated result back out.

    Implements the ``G -> C -> G`` coordination pattern from ScaFi (``BlocksWithGC.summarize``).

    Args:
        sink: True on sink/leader devices that aggregate the region's values.
        local: Local value contributed by each device.
        accumulation: Binary function combining two values.
        distances: Field of edge distances to neighbors. Defaults to ``hops_distance()``.
        spreading_strategy: Optional strategy for gradient and broadcast steps.
        collect_strategy: Optional strategy for the collection step.

    Returns:
        The aggregated value broadcast from the nearest ``sink``.
    """
    potential = distance_to(sink, distances, strategy=spreading_strategy)
    collected = collect_with(potential, local, accumulation, strategy=collect_strategy)
    return broadcast(sink, collected, distances, strategy=spreading_strategy)

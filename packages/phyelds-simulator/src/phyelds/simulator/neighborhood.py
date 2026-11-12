"""
Neighborhood functions for the phyelds simulator.
A neighborhood function is simply a function that takes a node and an environment,
and returns a list of neighbors.
"""

from collections import defaultdict
import heapq
import itertools
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

from phyelds.simulator import Environment, Node

_NEVER = object()  # the round a node has not adapted its range in yet
# Cells a little wider than the radius: a rounding error can never put a neighbor two cells off.
_MARGIN = 1 + 1e-6


class _UniformGrid:
    """
    The nodes of an environment by the cell of a uniform grid they are in: the nodes within
    ``side`` of a node are in its cell or in the cells around it. The nodes the grid cannot
    place, with a coordinate that is not a finite number or of another dimension than the
    first node, are near every node.
    """

    def __init__(self, side: float, nodes: Iterable[Node]):
        self.side = side
        self.rank: Dict[Any, int] = {}
        """The order of each node in the environment, by its id."""
        self._dimensions: Optional[int] = None
        self._cells: Dict[Tuple[int, ...], Dict[Any, Node]] = defaultdict(dict)
        self._anywhere: Dict[Any, Node] = {}
        self._next_rank = 0
        for node in nodes:
            self.added(node, None)

    def __len__(self) -> int:
        return len(self.rank)

    def cell_count(self) -> int:
        """How many non-empty grid cells currently hold nodes."""
        return len(self._cells)

    def anywhere_nodes(self) -> Iterable[Node]:
        """Nodes that could not be placed in a finite grid cell."""
        return self._anywhere.values()

    def cell_nodes(self, cell: Tuple[int, ...]) -> Iterable[Node]:
        """Nodes placed in ``cell``, or nothing when ``cell`` is empty."""
        bucket = self._cells.get(cell)
        return () if bucket is None else bucket.values()

    def cells_from_ring(
        self, center: Tuple[int, ...], min_ring: int
    ) -> Iterable[Node]:
        """Nodes in all non-empty cells at Chebyshev distance ``>= min_ring`` from ``center``."""
        for cell, bucket in self._cells.items():
            if max(abs(a - b) for a, b in zip(cell, center)) >= min_ring:
                yield from bucket.values()

    def all_nodes(self) -> List[Node]:
        """Every indexed node in the grid."""
        return [
            *self._anywhere.values(),
            *itertools.chain.from_iterable(nodes.values() for nodes in self._cells.values()),
        ]

    def added(self, node: Node, replaced: Optional[Node]) -> None:
        """Index ``node``; one that replaced another keeps its order, as in the environment."""
        if replaced is None:
            self.rank[node.id] = self._next_rank
            self._next_rank += 1
        else:
            self._drop_from_cell(replaced.position, node.id)
        self._bucket(node.position)[node.id] = node

    def removed(self, node: Node) -> None:
        """Forget ``node``."""
        self._drop_from_cell(node.position, node.id)
        self.rank.pop(node.id, None)

    def moved(self, node: Node, old_position: Tuple[float, ...]) -> None:
        """Index ``node`` in the cell of its position."""
        if node.id in self.rank:
            self._drop_from_cell(old_position, node.id)
            self._bucket(node.position)[node.id] = node

    def near(self, position: Tuple[float, ...], radius: Optional[float] = None) -> List[Node]:
        """The nodes that may be within ``radius`` (or ``side`` by default) of ``position``."""
        if radius is not None and not math.isfinite(radius):
            return self.all_nodes()
        cell = self.cell_of(position)
        if cell is None:
            return self.all_nodes()
        steps = 1 if radius is None else math.ceil(radius * _MARGIN / self.side)
        if (2 * steps + 1) ** len(cell) >= len(self._cells):
            return self.all_nodes()
        found = list(self._anywhere.values())
        for offset in itertools.product(range(-steps, steps + 1), repeat=len(cell)):
            around = tuple(index + step for index, step in zip(cell, offset))
            bucket = self._cells.get(around)
            if bucket:
                found.extend(bucket.values())
        return found

    def cell_of(self, position: Tuple[float, ...]) -> Optional[Tuple[int, ...]]:
        """The cell of ``position``, or ``None`` if the grid cannot place it."""
        try:
            if self._dimensions is None:
                self._dimensions = len(position)
            if len(position) != self._dimensions:
                return None
            return tuple(math.floor(coordinate / self.side) for coordinate in position)
        except (TypeError, ValueError, OverflowError):  # no length, NaN or infinite
            return None

    def _bucket(self, position: Tuple[float, ...]) -> Dict[Any, Node]:
        cell = self.cell_of(position)
        return self._anywhere if cell is None else self._cells[cell]

    def _drop_from_cell(self, position: Tuple[float, ...], node_id: Any) -> None:
        cell = self.cell_of(position)
        if cell is None:
            self._anywhere.pop(node_id, None)
            return
        bucket = self._cells.get(cell)
        if bucket is not None:
            bucket.pop(node_id, None)
            if not bucket:
                del self._cells[cell]


def radius_neighborhood(radius: float):
    """
    Create a neighborhood function that includes nodes within a certain radius.

    The nodes are found through a uniform grid that the environment keeps up to date as
    nodes move, join and leave, so a query reads only the nodes nearby. The neighbors are
    those of a scan of every node, in the order of the environment.
    """
    side = radius * _MARGIN if 0 < radius < math.inf else (math.inf if radius > 0 else 1.0)

    def neighborhood_func(node: Node, environment: Environment) -> List[Node]:
        grid = environment.spatial_index(("grid", side), lambda nodes: _UniformGrid(side, nodes))
        candidates = sorted(grid.near(node.position), key=lambda other: grid.rank[other.id])
        return [
            other for other in candidates
            if other.id != node.id and _distance(node, other) <= radius
        ]

    return neighborhood_func


def _knn_grid_side(nodes: List[Node], target_k: int) -> float:
    """Choose a uniform-grid cell size expecting roughly ``target_k`` nodes per cell."""
    mins: List[float] = []
    maxs: List[float] = []
    placed = 0
    for node in nodes:
        try:
            coords = [float(coord) for coord in node.position]
        except (TypeError, ValueError):
            continue
        if not coords or not all(math.isfinite(coord) for coord in coords):
            continue
        if not mins:
            mins, maxs = list(coords), list(coords)
        elif len(coords) != len(mins):
            continue
        else:
            for idx, coord in enumerate(coords):
                mins[idx] = min(mins[idx], coord)
                maxs[idx] = max(maxs[idx], coord)
        placed += 1
    if not mins or not maxs or placed <= 1:
        return 1.0
    spans = [high - low for low, high in zip(mins, maxs) if high > low]
    if not spans:
        return 1.0
    volume = math.prod(spans)
    return max(1e-6, (volume * min(max(1, target_k), placed) / placed) ** (1.0 / len(spans)))


def _ring_cells(center: Tuple[int, ...], ring: int) -> Iterable[Tuple[int, ...]]:
    """Grid cells at exact Chebyshev distance ``ring`` around ``center``."""
    if ring == 0:
        yield center
        return
    span = range(-ring, ring + 1)
    for offset in itertools.product(span, repeat=len(center)):
        if max(abs(step) for step in offset) == ring:
            yield tuple(index + step for index, step in zip(center, offset))


def _ring_lower_bound(
    position: Tuple[float, ...], cell: Tuple[int, ...], ring: int, side: float
) -> float:
    """Safe lower bound on Euclidean distance from ``position`` to any cell beyond ``ring``."""
    margin = min(
        min(coord - (idx - ring) * side, (idx + ring + 1) * side - coord)
        for coord, idx in zip(position, cell)
    )
    scale = 1.0 + max((abs(coord) for coord in position), default=0.0)
    return margin / _MARGIN - 1e-9 * scale


def _score_candidates(
    node_id: Any,
    origin: Tuple[float, ...],
    others: Iterable[Node],
    rank: Dict[Any, int],
) -> List[Tuple[bool, float, int, Node]]:
    """Rank candidate nodes by ``(isnan, distance_or_zero, environment_rank)``."""
    scored: List[Tuple[bool, float, int, Node]] = []
    for other in others:
        if other.id != node_id:
            dist = sum((a - b) ** 2 for a, b in zip(origin, other.position)) ** 0.5
            is_nan = math.isnan(dist)
            scored.append((is_nan, 0.0 if is_nan else dist, rank[other.id], other))
    return scored


def k_nearest_neighbors(k: int):
    """
    Create a neighborhood function that returns the ``k`` closest nodes.

    Ties in distance are broken by the order of the nodes in the environment. Queries use
    the environment's spatial grid, expanding outward from the node's cell only until no
    unvisited cell can contain a closer neighbor.
    """
    index_key = ("knn", max(1, k))

    def neighborhood_func(node: Node, environment: Environment) -> List[Node]:
        if k <= 0 or len(environment.nodes) <= 1:
            return []
        grid: _UniformGrid = environment.spatial_index(  # type: ignore[assignment]
            index_key, lambda nodes: _UniformGrid(_knn_grid_side(nodes, k), nodes)
        )
        try:
            origin = tuple(node.position)
        except TypeError:
            origin = ()
        cell = grid.cell_of(origin) if origin else None
        if cell is None or len(grid) - 1 <= k:
            scored_all = _score_candidates(node.id, origin, grid.all_nodes(), grid.rank)
            return [other for _, _, _, other in heapq.nsmallest(k, scored_all)]

        scored = _score_candidates(node.id, origin, grid.anywhere_nodes(), grid.rank)
        ring = 0
        while True:
            if (2 * ring + 1) ** len(cell) >= grid.cell_count():
                scored.extend(
                    _score_candidates(node.id, origin, grid.cells_from_ring(cell, ring), grid.rank)
                )
                return [other for _, _, _, other in heapq.nsmallest(k, scored)]
            for around in _ring_cells(cell, ring):
                scored.extend(
                    _score_candidates(node.id, origin, grid.cell_nodes(around), grid.rank)
                )
            if len(scored) >= k:
                scored = heapq.nsmallest(k, scored)
                if not scored[-1][0] and math.isfinite(scored[-1][1]) and (
                    scored[-1][1] < _ring_lower_bound(origin, cell, ring, grid.side)
                ):
                    return [other for _, _, _, other in scored]
            ring += 1

    return neighborhood_func


def full_neighborhood(node: Node, environment: Environment) -> List[Node]:
    """Include all nodes as neighbors"""
    all_nodes: List[Node] = environment.node_list()
    return [n for n in all_nodes if n.id != node.id]


def _distance(first: Node, second: Node) -> float:
    return sum((a - b) ** 2 for a, b in zip(first.position, second.position)) ** 0.5


class AdaptiveRange:
    """
    A neighborhood where each node has its own communication range, which adapts to keep
    about ``neighbors`` neighbors: a node with too many shrinks its range, one with too
    few grows it. A crowded swarm keeps its messages few, and a scattered one stays
    connected. Two nodes are neighbors if each is in range of the other.

    The rule of Alchemist's ``AdaptiveRange`` linking rule. A range adapts once per round
    of its node, a new value of its ``time``, so that drawing the edges changes nothing.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        radius: float,
        *,
        neighbors: int,
        tolerance: int,
        step: float = 1.0,
        min_range: float = 1.0,
        max_range: float = 100.0,
    ):
        if not min_range <= radius <= max_range:
            raise ValueError(f"the radius {radius} must be within [{min_range}, {max_range}]")
        if neighbors < 0 or tolerance < 0 or step <= 0:
            raise ValueError("counts must not be negative, and the step must be positive")
        self.radius = radius
        # the fewest and the most neighbors a node keeps its range with
        self._wanted = (max(1, neighbors - tolerance), neighbors + tolerance)
        self.step = step
        self.min_range = min_range
        self.max_range = max_range
        self.ranges: Dict[Any, float] = {}
        self._adapted_at: Dict[Any, Any] = {}

    def range_of(self, node: Node) -> float:
        """The current communication range of ``node``."""
        return self.ranges.get(node.id, self.radius)

    def __call__(self, node: Node, environment: Environment) -> List[Node]:
        reach = self.range_of(node)
        side = self.radius * _MARGIN if 0 < self.radius < math.inf else 1.0
        grid: _UniformGrid = environment.spatial_index(  # type: ignore[assignment]
            ("grid", side), lambda nodes: _UniformGrid(side, nodes)
        )
        candidates = sorted(
            grid.near(node.position, radius=reach), key=lambda other: grid.rank[other.id]
        )
        found = [
            other for other in candidates
            if other.id != node.id
            and _distance(node, other) <= min(reach, self.range_of(other))
        ]
        time = node.data.get("time")
        if self._adapted_at.get(node.id, _NEVER) != time:
            self._adapted_at[node.id] = time
            fewest, most = self._wanted
            if len(found) > most:
                self.ranges[node.id] = max(reach - self.step, self.min_range)
            elif len(found) < fewest:
                self.ranges[node.id] = min(reach + self.step, self.max_range)
        return found


def adaptive_range(  # pylint: disable=too-many-arguments
    radius: float,
    *,
    neighbors: int,
    tolerance: int,
    step: float = 1.0,
    min_range: float = 1.0,
    max_range: float = 100.0,
) -> AdaptiveRange:
    """
    Create a neighborhood whose ranges adapt to keep about ``neighbors`` neighbors.

    Args:
        radius: The range each node starts with.
        neighbors: The number of neighbors each node aims at.
        tolerance: How many more or fewer neighbors are fine: a node shrinks its range
            above ``neighbors + tolerance`` and grows it below ``neighbors - tolerance``
            (at least one).
        step: How much a range changes in a round.
        min_range: The shortest range.
        max_range: The longest range.

    Returns:
        The neighborhood function, whose ``range_of(node)`` is the range of a node.

    Raises:
        ValueError: If ``radius`` is out of bounds, a count is negative or ``step`` is not
            positive.
    """
    return AdaptiveRange(
        radius, neighbors=neighbors, tolerance=tolerance, step=step,
        min_range=min_range, max_range=max_range,
    )

"""
Neighborhood functions for the phyelds simulator.
A neighborhood function is simply a function that takes a node and a list of all nodes,
and returns a list of neighbors.
"""

from typing import Any, Dict, List
from phyelds.simulator import Node, Environment

_NEVER = object()  # the round a node has not adapted its range in yet


def radius_neighborhood(radius: float):
    """Create a neighborhood function that includes nodes within a certain radius"""

    def neighborhood_func(node: Node, environment: Environment) -> List[Node]:
        all_nodes: List[Node] = environment.node_list()
        neighbors = []
        for other in all_nodes:
            if other.id == node.id:  # Skip self
                continue

            # Calculate Euclidean distance
            distance = (
                sum((a - b) ** 2 for a, b in zip(node.position, other.position)) ** 0.5
            )

            if distance <= radius:
                neighbors.append(other)
        return neighbors

    return neighborhood_func


def k_nearest_neighbors(k: int):
    """Create a neighborhood function that includes the k nearest nodes"""

    def neighborhood_func(node: Node, environment: Environment) -> List[Node]:
        all_nodes: List[Node] = environment.node_list()
        others = [n for n in all_nodes if n.id != node.id]
        if not others:
            return []

        # Calculate distances
        distances = [
            (
                sum((a - b) ** 2 for a, b in zip(node.position, other.position)) ** 0.5,
                other,
            )
            for other in others
        ]

        # Sort by distance and take k nearest
        distances.sort()
        return [other for _, other in distances[:k]]

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
        found = [
            other for other in environment.node_list()
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

"""
Neighborhood functions for the phyelds simulator.
A neighborhood function is simply a function that takes a node and a list of all nodes,
and returns a list of neighbors.
"""

from typing import List

from phyelds.simulator import Node


def radius_neighborhood(radius: float):
    """Create a neighborhood function that includes nodes within a certain radius"""

    def neighborhood_func(node: Node, all_nodes: List[Node]) -> List[Node]:
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

    def neighborhood_func(node: Node, all_nodes: List[Node]) -> List[Node]:
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


def full_neighborhood(node: Node, all_nodes: List[Node]) -> List[Node]:
    """Include all nodes as neighbors"""
    return [n for n in all_nodes if n.id != node.id]

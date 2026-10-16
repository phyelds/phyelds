"""
This module contains functions to calculate distances between nodes in the neighborhood.
These functions may be used by other library to compute system-wise properties
"""

from collections.abc import Sequence
import math

from phyelds.calculus import neighbors, aggregate
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id, local_position


@aggregate
def neighbors_distances(
    position: Sequence[float] | None = None,
) -> NeighborhoodField[float]:
    """
    Compute the Euclidean distance to each neighbor in the neighborhood.

    Args:
        position: Optional coordinate sequence for the current node. When
            omitted, ``local_position()`` is used. Supports any dimension
            (2D, 3D, N-D).

    Returns:
        A ``NeighborhoodField[float]`` with the distance to each neighbor
        (0.0 for the local node).
    """
    my_position = tuple(local_position() if position is None else position)
    positions: NeighborhoodField[tuple[float, ...]] = neighbors(my_position)
    return positions.map(lambda other: math.dist(my_position, other))


@aggregate
def hops_distance() -> NeighborhoodField[int]:
    """
    Get the hops distance to the neighbors from the current node.
    :return: the neighborhood representing the hops distance to the neighbors
    """
    distances: NeighborhoodField[int] = neighbors(1)
    distances.data[local_id()] = 0
    return distances

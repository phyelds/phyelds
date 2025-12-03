"""
This module contains functions to calculate distances between nodes in the neighborhood.
These functions may be used by other library to compute system-wise properties
"""

from phyelds.calculus import neighbors, aggregate
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id, local_position


@aggregate
def neighbors_distances() -> NeighborhoodField[float]:
    """
    Get the distances to the neighbors from the current node.
    :return: the neighborhood representing the distances to the neighbors
    """
    positions: NeighborhoodField = neighbors(local_position())
    x, y = local_position()
    return positions.map(lambda v: ((v[0] - x) ** 2 + (v[1] - y) ** 2) ** 0.5)


@aggregate
def hops_distance() -> NeighborhoodField[int]:
    """
    Get the hops distance to the neighbors from the current node.
    :return: the neighborhood representing the hops distance to the neighbors
    """
    distances: NeighborhoodField[int] = neighbors(1)
    distances.data[local_id()] = 0
    return distances

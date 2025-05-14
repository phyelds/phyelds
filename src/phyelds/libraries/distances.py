"""
This module contains functions to calculate distances between nodes in the neighborhood.
These functions may be used by other library to compute system-wise properties
"""

from phyelds.calculus import neighbors, aggregate
from phyelds.libraries.device import local_id, local_position


@aggregate
def neighbors_distances():
    """
    Get the distances to the neighbors from the current node.
    :param position: the current node position
    :return: the field representing the distances to the neighbors
    """
    positions = neighbors(local_position())
    x, y = local_position()
    return positions.map(lambda v: ((v[0] - x) ** 2 + (v[1] - y) ** 2) ** 0.5)


@aggregate
def hops_distance():
    """
    Get the hops distance to the neighbors from the current node.
    :return: the field representing the hops distance to the neighbors
    """
    distances = neighbors(1)
    distances.data[local_id()] = 0
    return distances

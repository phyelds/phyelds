"""
This module contains functions to calculate distances between nodes in the neighborhood.
These functions may be used by other library to compute system-wise properties
"""

from phyelds.calculus import neighbors, aggregate
from phyelds.data import Field
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
    distances = {}
    for node_id, pos in positions.data.items():
        # pos are x, y tuples
        n_x, n_y = pos
        distances[node_id] = ((x - n_x) ** 2 + (y - n_y) ** 2) ** 0.5
    return Field(distances, local_id())


@aggregate
def hops_distance():
    """
    Get the hops distance to the neighbors from the current node.
    :return: the field representing the hops distance to the neighbors
    """
    distances = neighbors(1)
    distances.data[local_id()] = 0
    return distances

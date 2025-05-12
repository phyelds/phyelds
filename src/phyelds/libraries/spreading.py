"""
Diffusion (information) library for phyelds
This library provides functions for diffusion of information in a network.
It includes functions for calculating distances and to braodcast information
"""
from phyelds.calculus import aggregate, remember, neighbors
from phyelds.data import Field
from phyelds.libraries.utils import min_with_default


@aggregate
def distance_to(source: bool, distances: Field) -> float:
    """
    Calculate the distance to a source node in the network.
    :param source:
    :param distances:
    :return:
    """
    gradient = remember(float("inf"))
    neighbors_gradients = neighbors(gradient) + distances
    return gradient.update(
        0.0
        if source
        else min_with_default(neighbors_gradients.exclude_self(), float("inf"))
    )


def cast_from(source: bool, data: any, accumulation: callable, distances: Field) -> any:
    """
    Cast information from a source node to its neighbors.
    :param source: the source node to cast from
    :param data: the data to cast
    :param accumulation: the function to accumulate the data
    :param distances: the distances against the neighbors
    :return: the data cast
    """
    cast_area = remember(data)
    potential = distance_to(source, distances)
    neighbors_value = neighbors(cast_area)
    # neighbors potential
    neighbors_potential = neighbors(potential)
    # take the value from the minimum potential
    values = zip(neighbors_potential, neighbors_value)
    # select the minimum potential
    _, result = min(values, key=lambda x: x[0])
    if source:
        return cast_area.update(data)
    return cast_area.update(accumulation(result))


@aggregate
def broadcast(source: bool, data: any, distances: Field) -> any:
    """
    Broadcast information to the network from a source node.
    :param source: the source node to broadcast from
    :param data: the data to spread
    :param distances: the distances again the neighbors
    :return: the data spread
    """
    return cast_from(source, data, lambda x: x, distances)

"""
Leader election functionality (self-stabilizing) using UUIDs.
"""
import random
from typing import Tuple
from phyelds.data import NeighborhoodField, StateT
from phyelds.libraries.device import local_id
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.utils import min_with_default
from phyelds.calculus import aggregate, remember, neighbors


@aggregate
def elect_leaders(area: float, distances: NeighborhoodField[float]) -> bool:
    """
    Elect a leader in the network using a random UUID.
    :param area: the area of the network
    :param distances: the distances to the neighbors
    :return: the current id of the leader
    """
    result: Tuple[StateT[float], int] = breaking_using_uids(random_uuid(), area, distances)
    # Return None if no leader was elected (infinite distance), otherwise return the leader ID
    return result[1] == local_id() and result[0] != (float("inf"))


@aggregate
def random_uuid() -> Tuple[StateT[float], int]:
    """
    Generate a random UUID for the node.
    :return: the random UUID
    """
    _, value = remember(random.random())
    return value, local_id()


@aggregate
def breaking_using_uids(
    uid: Tuple[StateT[float], int],
    area: float,
    distances: NeighborhoodField[float]
) -> StateT[tuple[float, int]]:
    """
    Break the symmetry using the UUID of the node.
    :param uid: the UUID of the node
    :param area: the area of the network
    :param distances: the distances to the neighbors
    :return: the current id of the leader
    """
    # get the minimum value of the neighbors
    set_lead, lead = remember(uid)
    # get the minimum value of the neighbors
    potential: float = distance_to(lead == uid, distances)
    new_lead: Tuple[float, int] = distance_competition(potential, area, uid, lead, distances)
    # if the new lead is the same, return the uid
    set_lead(new_lead)
    return lead


@aggregate
def distance_competition(
    current_distance: float,
    area: float,
    uid: Tuple[StateT[float], int],
    lead: StateT[Tuple[float, int]],
    distances: NeighborhoodField[float]
) -> StateT[Tuple[float, int]]:
    """
    Compare the distance of the current node with the distance of the neighbors.
    It leverages the fact that the tuple is a symmetric breaker.
    :param current_distance: current distance to the lead
    :param area: the maximum distance to the lead
    :param uid: the local id of the node
    :param lead: the current lead
    :param distances: the distances to the neighbors
    :return: the new lead
    """
    inf: Tuple[float, int] = (float("inf"), uid[1])
    # neighbors lead
    neighbors_lead: NeighborhoodField[Tuple[float, int]] = neighbors(lead)
    condition: NeighborhoodField[bool] = (neighbors(current_distance) + distances) < (0.5 * area)
    # filter the one that have the condition
    lead_filtered: list[Tuple[float, int]] = neighbors_lead.select(condition)
    # take the minimum value, but the comparator just consider both values of the tuple
    result: Tuple[float, int] = min_with_default(lead_filtered, uid)
    if current_distance > area:
        return uid
    if current_distance >= (0.5 * area):
        return inf
    return result

"""
Leader election functionality (self-stabilizing) using UUIDs.
"""
import random
from phyelds.data import Field
from phyelds.libraries.device import local_id
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.utils import min_with_default
from phyelds.calculus import aggregate, remember, neighbors


@aggregate
def elect_leaders(area: float, distances: Field) -> bool:
    """
    Elect a leader in the network using a random UUID.
    :param area: the area of the network
    :param distances: the distances to the neighbors
    :return: the current id of the leader
    """
    result = breaking_using_uids(random_uuid(), area, distances)
    # Return None if no leader was elected (infinite distance), otherwise return the leader ID
    return result[1] == local_id() and result[0] != (float("inf"))


@aggregate
def random_uuid():
    """
    Generate a random UUID for the node.
    :return: the random UUID
    """
    value = remember(random.random())
    return value, local_id()


@aggregate
def breaking_using_uids(uid, area: float, distances: Field):
    """
    Break the symmetry using the UUID of the node.
    :param uid: the UUID of the node
    :param area: the area of the network
    :param distances: the distances to the neighbors
    :return: the current id of the leader
    """
    # get the minimum value of the neighbors
    lead = remember(uid)
    # get the minimum value of the neighbors
    potential = distance_to(lead == uid, distances)
    new_lead = distance_competition(potential, area, uid, lead, distances)
    # if the new lead is the same, return the uid
    return lead.update(new_lead)


@aggregate
def distance_competition(
    current_distance, area: float, uid, lead, distances: Field
):
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
    inf = (float("inf"), uid[1])
    # neighbors lead
    neighbors_lead = neighbors(lead)
    condition = (neighbors(current_distance) + distances) < (0.5 * area)
    # filter the one that have the condition
    lead = neighbors_lead.select(condition)
    # take the minimum value, but the comparator just consider both values of the tuple
    lead = min_with_default(lead, uid)
    if current_distance > area:
        return uid
    if current_distance >= (0.5 * area):
        return inf
    return lead

from fieldpy.calculus import aggregate, remember, neighbors
from fieldpy.data import Field
import random

from fieldpy.libraries.spreading import distance_to, broadcast
from fieldpy.libraries.utils import min_with_default


@aggregate
def elect_leader(context, area: float, distances: Field) -> int:
    result = breaking_using_uids(random_uuid(context), area, distances)
    # Return None if no leader was elected (infinite distance), otherwise return the leader ID
    return None if result[0] == float("inf") else result[1]


@aggregate
def random_uuid(context):
    value = remember(random.random())
    return (value, context.id)


@aggregate
def breaking_using_uids(uid, area: float, distances: Field):
    # get the minimum value of the neighbors
    lead = remember(uid)
    # get the minimum value of the neighbors
    potential = distance_to(lead == uid, distances)
    leader_id = broadcast(lead == uid, uid, distances)
    new_lead = distance_competition(potential, area, uid, lead, distances, leader_id)
    # if the new lead is the same, return the uid
    return lead.update(new_lead)


@aggregate
def distance_competition(
    current_distance, area: float, uid, lead, distances: Field, leader_id
):
    inf = (float("inf"), uid[1])
    # neighbors lead
    neighbors_lead = neighbors(lead)
    condition = (neighbors(current_distance) + distances) < (0.5 * area)
    # filter the one that have the condition
    lead = neighbors_lead.select(condition)
    # take the minimum value, but the comparator just consider both values of the tuple
    lead = min_with_default(lead, inf)
    if current_distance > area:
        return uid
    elif current_distance >= (0.5 * area):
        return inf
    else:
        return lead

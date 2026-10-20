"""
Opinions: the network agrees on the share of devices that vote yes, the same on every device.

A leader is elected; the votes flow to it along a gradient, where they are averaged, and
the leader spreads the share back. Switch `vote` on or off: every device sees the new
share. Watch `nearby`: gossip_mean averages each vote with those around it, a local
opinion that differs from device to device.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.collect import mean_values
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.gossip import gossip_mean
from phyelds.libraries.leader_election import elect_leader
from phyelds.libraries.spreading import broadcast, distance_to

AREA = 100.0  # how far a leader rules: wider than the arena, so there is one


@aggregate
def share() -> float:
    """The share of the devices that vote yes, as the leader averages it."""
    vote = 1.0 if sense("vote") else 0.0
    nearby = gossip_mean(vote)  # noqa: F841 (not returned, but there to watch)
    distances = neighbors_distances()
    is_leader = elect_leader(AREA, distances) == local_id()
    mean = mean_values(distance_to(is_leader, distances), vote)
    return broadcast(is_leader, mean, distances)

"""
The programs the benchmarks run. Hosts that load a program by name, as ARGoS and Webots
controllers do, import them as ``programs:<name>``.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to


@aggregate
def empty():
    """Nothing: what the adapter and the engine cost on their own."""
    return None


@aggregate
def gradient():
    """Hops to the source."""
    return distance_to(sense("source"))


@aggregate
def gossip():
    """The largest id in the network."""
    return gossip_max(local_id())


@aggregate
def count():
    """The number of devices, collected towards the source."""
    return count_nodes(distance_to(sense("source")))

"""
Census: every device knows how many devices the network has, counted at the source.

The devices count themselves up a gradient towards the source, which spreads the total
back: add devices, or take some away, and the number follows. Watch `here`, the devices
each one counts on its way to the source.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import broadcast, distance_to


@aggregate
def census() -> int:
    """How many devices the source counts, as the source spreads it."""
    distances = neighbors_distances()
    source = sense("source")
    here = count_nodes(distance_to(source, distances))
    return broadcast(source, here, distances)

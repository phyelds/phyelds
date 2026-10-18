"""
Channel: the devices between a source and a target form a band along the shortest path.

A device belongs to it when the shortest trip from the source to the target through it is at
most WIDTH longer than the shortest path: watch to_source, to_target and between.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_between, distance_to

WIDTH = 0.8  # how much longer than the shortest path a trip through the channel may be


@aggregate
def channel() -> bool:
    """Whether the shortest trip from the source to the target through the device is at most WIDTH longer."""
    source, target = sense("source"), sense("target")
    distances = neighbors_distances()
    to_source = distance_to(source, distances)
    to_target = distance_to(target, distances)
    between = distance_between(source, target, distances)
    return to_source + to_target <= between + WIDTH

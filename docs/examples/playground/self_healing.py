"""
Self-healing: move the source, and the gradient repairs itself.

Drag the source, or switch `source` on for another device and off for the first one:
nobody tells the devices, they find out from their neighbours.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


@aggregate
def gradient() -> float:
    """The distance from the nearest device whose `source` sensor is on."""
    return distance_to(sense("source"), neighbors_distances())

"""
Gradient: every device estimates its distance from the nearest source.

The field grows from the source, one round at a time, through neighbours only.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


@aggregate
def gradient() -> float:
    """The distance from the nearest device whose `source` sensor is on."""
    return distance_to(sense("source"), neighbors_distances())

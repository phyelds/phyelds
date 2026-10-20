"""
Trail: the devices the source passed near stay lit, the network remembers where it went.

A device is near the source within NEAR; `previously` holds from the first round it was
on. Drag the source around to paint a trail, and switch `source` on elsewhere to start
another one.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.logic import previously
from phyelds.libraries.spreading import distance_to

NEAR = 1.0  # how close to the source a device is near it


@aggregate
def trail() -> bool:
    """Whether the source was ever within NEAR of the device."""
    near = distance_to(sense("source"), neighbors_distances()) <= NEAR
    return previously(near)

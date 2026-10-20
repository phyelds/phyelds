"""
Spread: the swarm gathers where `gather` is on, and spreads out over the arena when it is off.

Each device heads to the nearest device sensing `gather`, which stays still, keeping
CLOSE from the others; without any, it moves away from the devices closer than SPREAD.
Switch `gather` off and the swarm spreads; switch it on for another device and the
swarm gathers there. Watch `gathering`: the network learns at once that no device
senses `gather` any more.
"""
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector, separation, sink_at
from phyelds.libraries.device import Sensor, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to, path_coherent

SPREAD = 0.9  # how close two devices may be, spread out
CLOSE = 0.35  # and gathered

gather: Sensor[bool] = Sensor("gather")


@aggregate
def spread() -> Vector:
    """Gather, if any device says so, else spread out: the velocity the device moves by."""
    here = gather.sense()
    # path_coherent forgets a device that stops sensing gather at once, not little by little.
    gathering = distance_to(here, neighbors_distances(), strategy=path_coherent()) < float("inf")
    towards = sink_at(here) if gathering else Vector()
    apart = separation(Vector(), within=CLOSE if gathering else SPREAD)
    return velocity.send(Vector() if here else towards + apart * 1.5)

"""
Flock: the leader wanders around the arena, and the swarm moves as it moves, together.

Every device takes the velocity of the leader, plus a pull towards it and a push away
from the devices too close. Drag the leader somewhere else, or switch `leader` on for
another device.
"""
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector, align_with_leader, explore, separation, sink_at
from phyelds.libraries.device import Sensor, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

LOWEST, HIGHEST = (0.5, 0.5), (4.5, 4.5)  # where the leader wanders, inside the arena
SPACING = 0.5  # how far a device keeps from the others

leader: Sensor[bool] = Sensor("leader")


@aggregate
def flock() -> float:
    """Move as the leader, close to it and apart from the others; the distance from it."""
    is_leader = leader.sense()
    heading = align_with_leader(is_leader, explore(LOWEST, HIGHEST))
    keep = sink_at(is_leader) * 0.5 + separation(Vector(), within=SPACING) * 2
    velocity.send(heading if is_leader else heading + keep)
    return distance_to(is_leader, neighbors_distances())

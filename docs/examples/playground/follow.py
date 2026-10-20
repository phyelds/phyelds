"""
Follow: the swarm heads to its leader along the network, each device keeping apart from the others.

Every device follows the shortest path to the leader, and keeps SPACING from its
neighbours. Drag the leader and the swarm follows it; switch `leader` on for another
device, and the swarm splits between the two. Watch `heading`, or `sink_at(is_leader)`.
"""
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector, separation, sink_at
from phyelds.libraries.device import Sensor, velocity

SPACING = 0.5  # how far a device keeps from the others

leader: Sensor[bool] = Sensor("leader")


@aggregate
def follow() -> Vector:
    """Head to the leader, keeping apart: the velocity the device moves by."""
    is_leader = leader.sense()
    # Every device runs sink_at, the leader too: it is where the paths start.
    heading = sink_at(is_leader) + separation(Vector(), within=SPACING, nearest=2) * 2
    return velocity.send(Vector() if is_leader else heading)

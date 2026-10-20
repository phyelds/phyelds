"""
Mission: the swarm gathers around its leader, crosses the arena to the target with it, then turns around it.

The phases are a collective state machine. Switch `go` on for any device: the swarm
leaves, and turns once the leader reaches the target. Restart (R) to start over. The
colour is the phase: 0 gather, 1 cross, 2 circle.
"""
from enum import IntEnum

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import StateMachine
from phyelds.experimental.swarm import Vector, align_with_leader, separation, sink_at, spin_around
from phyelds.libraries.device import Sensor, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time

SPACING = 0.5  # how far a drone keeps from the others
ARRIVED = 1.0  # how close to the target the leader has arrived

leader: Sensor[bool] = Sensor("leader")
target: Sensor[bool] = Sensor("target")
go: Sensor[bool] = Sensor("go")


class Phase(IntEnum):
    """The phases of the mission."""

    GATHER = 0
    CROSS = 1
    CIRCLE = 2


mission = StateMachine(*Phase)


def moving(towards: Vector) -> Vector:
    """Head ``towards``, keeping apart from the other drones; the target stays where it is."""
    return Vector() if target.sense() else towards + separation(Vector(), within=SPACING) * 2


@mission.state(Phase.GATHER, to=[Phase.CROSS])
def gather() -> Vector:
    """Head to the leader, until a drone says to go."""
    if go.sense():
        mission.go(Phase.CROSS, priority=-local_time())
    heading = moving(sink_at(leader.sense()))
    return Vector() if leader.sense() else heading


@mission.state(Phase.CROSS, to=[Phase.CIRCLE])
def cross() -> Vector:
    """The leader heads to the target, the others move as it does, close to it."""
    to_target = sink_at(target.sense())
    arrived = distance_to(target.sense(), neighbors_distances()) <= ARRIVED
    if leader.sense() and arrived:
        mission.go(Phase.CIRCLE, priority=-local_time())
    heading = align_with_leader(leader.sense(), to_target)
    return moving(heading + sink_at(leader.sense()) * 0.3)


@mission.state(Phase.CIRCLE)
def circle() -> Vector:
    """Turn around the leader, close to it."""
    around = moving(spin_around(leader.sense()) + sink_at(leader.sense()) * 0.3)
    return Vector() if leader.sense() else around


@aggregate
def drone() -> int:
    """The phase the drone agrees on; it moves as the phase says."""
    phase, heading = mission.run()
    velocity.send(heading)
    return int(phase)

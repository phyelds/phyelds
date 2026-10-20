"""
Mission: the swarm gathers around its leader, crosses the arena with it, turns around it, and starts over.

The phases are a collective state machine that the leader moves on: after GATHERING
rounds it heads for the opposite corner, and once there the swarm turns around it for
CIRCLING rounds, then gathers again. Drag the leader to send the swarm elsewhere, and
watch `mission.run()` for the phase.
"""
from enum import IntEnum

from phyelds.calculus import aggregate, remember
from phyelds.experimental.state_machines import StateMachine
from phyelds.experimental.swarm import Vector, align_with_leader, go_to, is_close, separation, sink_at, spin_around
from phyelds.libraries.device import Sensor, local_position, velocity
from phyelds.libraries.time import local_time, timer

ARENA = 5.0  # the side of the arena of the playground
GATHERING = 15  # rounds the swarm gathers before crossing
CIRCLING = 25  # rounds it turns around the leader before gathering again
SPACING = 0.4  # how far a drone keeps from the others

leader: Sensor[bool] = Sensor("leader")


class Phase(IntEnum):
    """The phases of the mission."""

    GATHER = 0
    CROSS = 1
    CIRCLE = 2


mission = StateMachine(*Phase)


def moving(towards: Vector) -> Vector:
    """Head ``towards``, keeping apart from the other drones."""
    return towards + separation(Vector(), within=SPACING) * 1.5


def after(rounds: float, phase: Phase) -> None:
    """Go to ``phase`` once the leader has spent ``rounds`` rounds in this one."""
    over = timer(rounds) <= 0
    if leader.sense() and over:
        mission.go(phase, priority=-local_time())


@mission.state(Phase.GATHER, to=[Phase.CROSS])
def gather() -> Vector:
    """Head to the leader, which waits."""
    after(GATHERING, Phase.CROSS)
    heading = moving(sink_at(leader.sense()))
    return Vector() if leader.sense() else heading


@mission.state(Phase.CROSS, to=[Phase.CIRCLE])
def cross() -> Vector:
    """The leader heads for the corner opposite to where it was, the others move as it does."""
    x, y = local_position()
    _, goal = remember((min(4.2, max(0.8, ARENA - x)), min(4.2, max(0.8, ARENA - y))))
    if leader.sense() and is_close(goal.value, 0.3):
        mission.go(Phase.CIRCLE, priority=-local_time())
    heading = align_with_leader(leader.sense(), go_to(goal.value))
    return heading if leader.sense() else moving(heading + sink_at(leader.sense()) * 0.5)


@mission.state(Phase.CIRCLE, to=[Phase.GATHER])
def circle() -> Vector:
    """Turn around the leader, close to it."""
    after(CIRCLING, Phase.GATHER)
    around = moving(spin_around(leader.sense()) + sink_at(leader.sense()) * 0.4)
    return Vector() if leader.sense() else around


@aggregate
def drone() -> Vector:
    """Move as the phase the drone agrees on says: the velocity the drone moves by."""
    _, heading = mission.run()
    return velocity.send(heading)

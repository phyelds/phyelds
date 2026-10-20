"""
Mission: the swarm gathers around its leader, crosses the arena with it, turns around it, and starts over.

The phases are a collective state machine that the leader moves on: after GATHERING
rounds it heads across the arena, and once there the swarm turns around it for
CIRCLING rounds, then gathers again. The arrows are the headings; the layer under them is
the phase each device is in, as the change spreads. Drag the leader to send the swarm
elsewhere.
"""
from enum import IntEnum

from phyelds.calculus import aggregate, remember
from phyelds.experimental.state_machines import StateMachine
from phyelds.experimental.swarm import Vector, align_with_leader, go_to, is_close, separation, sink_at, spin_around
from phyelds.libraries.device import Sensor, local_position, velocity
from phyelds.libraries.time import local_time, timer

CENTRE = 2.5  # the centre of the arena of the playground
FARTHEST = 4.0  # how far from the centre the leader goes, inside the world of the playground
GATHERING = 25  # rounds the swarm gathers before crossing
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
    """The leader heads across the centre, to the opposite side; the others move as it does."""
    x, y = local_position()
    _, goal = remember(tuple(CENTRE + max(-FARTHEST, min(FARTHEST, CENTRE - value)) for value in (x, y)))
    if leader.sense() and is_close(goal.value, 0.3):
        mission.go(Phase.CIRCLE, priority=-local_time())
    heading = align_with_leader(leader.sense(), go_to(goal.value))
    return heading if leader.sense() else moving(heading + sink_at(leader.sense()))


@mission.state(Phase.CIRCLE, to=[Phase.GATHER])
def circle() -> Vector:
    """Turn around the leader, close to it."""
    after(CIRCLING, Phase.GATHER)
    around = moving(spin_around(leader.sense()) + sink_at(leader.sense()))
    return Vector() if leader.sense() else around


@aggregate
def drone() -> Vector:
    """Move as the phase the drone agrees on says: the velocity the drone moves by."""
    phase, heading = mission.run()  # watch phase
    return velocity.send(heading)

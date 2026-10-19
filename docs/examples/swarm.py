"""
A swarm of drones on a mission, its phases a collective state machine, its moves swarm blocks.

The drones gather around their leader, cross the field with it, keeping apart, then
circle around it. Only the leader senses when to go on; the state machine spreads each
phase to the swarm. Run it to regenerate the animation in ``docs/assets``, in the light
theme of the docs and, with ``-dark`` in its name, in the dark one (smaller if
``gifsicle`` is on the PATH):

    poetry run python docs/examples/swarm.py
"""
import random
import shutil
import subprocess
from enum import IntEnum
from pathlib import Path
from typing import Literal

from matplotlib import pyplot as plt

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import StateMachine
from phyelds.experimental.swarm import (
    Vector, align_with_leader, go_to, separation, sink_at, spin_around,
)
from phyelds.libraries.device import sense, store
from phyelds.libraries.time import local_time
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator import Environment
from phyelds.simulator.effects import DrawEdges, DrawNodes, Effect, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import adaptive_range
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

ASSETS = Path(__file__).resolve().parent.parent / "assets"
THEMES = {"": {}, "-dark": Path(__file__).resolve().parent / "dark.mplstyle"}
SEED = 3
DRONES = 30
LEADER = 0
RANGE = 4.0  # the communication range a drone starts with, adapted to keep about 12 neighbors
SPACING = 1.2  # how far the drones keep from each other
TARGET = (12.0, 12.0)  # where the leader heads
SPEED = 0.25  # the top speed of a drone, per time unit
EVENTS = {40: "go", 110: "circle"}  # when the leader senses it is time to go on
END = 170
LIMITS = (-8.0, 18.0)


# --8<-- [start:swarm]
class Phase(IntEnum):
    """The phases of the mission."""

    GATHER = 0
    CROSS = 1
    CIRCLE = 2


mission = StateMachine(*Phase)


def moving(towards: Vector) -> Vector:
    """Head ``towards``, keeping apart from the other drones."""
    return (towards + separation(Vector(), within=SPACING) * 1.5).normalize()


@mission.state(Phase.GATHER, to=[Phase.CROSS])
def gather() -> Vector:
    """Head to the leader, until it says to go."""
    if sense("go"):
        mission.go(Phase.CROSS, priority=-local_time())
    return moving(sink_at(sense("leader")))


@mission.state(Phase.CROSS, to=[Phase.CIRCLE])
def cross() -> Vector:
    """The leader heads to the target, the others move as it does, close to it."""
    if sense("circle"):
        mission.go(Phase.CIRCLE, priority=-local_time())
    leader = sense("leader")
    heading = align_with_leader(leader, go_to(TARGET) if leader else Vector())
    return moving(heading + sink_at(leader) * 0.3)


@mission.state(Phase.CIRCLE)
def circle() -> Vector:
    """Turn around the leader, close to it."""
    leader = sense("leader")
    # Every drone runs the blocks, the leader too: it is the source of their gradients.
    turning = moving(spin_around(leader) + sink_at(leader) * 0.3)
    return Vector() if leader else turning


@aggregate
def drone() -> Phase:
    """The program every drone runs: the phase it agrees on, and where it moves."""
    phase, velocity = mission.run()
    store("velocity", velocity)
    return phase
# --8<-- [end:swarm]


def sense_event(simulator: Simulator, event: str) -> None:
    """The leader senses that it is time to go on."""
    simulator.environment.nodes[LEADER].data[event] = True


def scene() -> Simulator:
    """The drones, scattered in a corner, with the events of the leader scheduled."""
    random.seed(SEED)
    simulator = Simulator()
    for node_id in range(DRONES):
        simulator.create_node((random.uniform(-6, 4), random.uniform(-6, 4)), node_id=node_id)
    simulator.environment.set_neighborhood_function(
        adaptive_range(RANGE, neighbors=12, tolerance=6, step=0.1, min_range=2.0, max_range=8.0)
    )
    simulator.environment.add_data_for_all_nodes({"leader": False, "go": False, "circle": False})
    simulator.environment.nodes[LEADER].data["leader"] = True
    schedule_program_for_all(simulator, 0.0, 1.0, drone)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=SPEED)
    for time, event in EVENTS.items():
        simulator.schedule_event(time - 0.5, sense_event, simulator, event)
    return simulator


class EqualAspect(Effect):
    """Draw the field with the same scale on both axes."""

    type: Literal["EqualAspect"] = "EqualAspect"

    def apply(self, ax, environment: Environment):
        ax.set_aspect("equal")


def record(simulator: Simulator, name: str) -> None:
    """Save the run to ``docs/assets/<name>``, a colour for each phase."""
    effects = [
        EqualAspect(), DrawEdges(alpha=0.2),
        DrawNodes(color_from="result", cmap="tab10", vmin=0.0, vmax=9.0),
    ]
    config = RenderConfig(
        effects=effects, dt=2.0, fps=10, mode=RenderMode.SAVE, save_as=str(ASSETS / name),
        xlim=LIMITS, ylim=LIMITS, show_axis=False, title="Swarm mission",
    )
    RenderMonitor(simulator, config)


def main() -> None:
    """Regenerate the animation of the swarm, in both themes."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix, style in THEMES.items():
        with plt.style.context(style):
            simulator = scene()
            record(simulator, f"swarm{suffix}.gif")
            simulator.run(END)
        if shutil.which("gifsicle"):
            gif = str(ASSETS / f"swarm{suffix}.gif")
            subprocess.run(["gifsicle", "-O3", "--colors", "64", "--batch", gif], check=True)


if __name__ == "__main__":
    main()

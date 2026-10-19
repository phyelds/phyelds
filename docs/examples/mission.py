"""
A search-and-rescue mission run as a collective state machine, on a lattice of drones.

The case study of the collective state machines, without the movement: the drones wait at
the base, explore when an alarm goes off, rescue when one of them finds the target, and
defend the base, before anything else, when it is attacked. Each event is sensed by one
drone only, and the machine spreads its transition to all of them; in each phase, a drone
also computes how far it is from where it heads. Run it to regenerate
the animation in ``docs/assets``, in the light theme of the docs and, with ``-dark`` in
its name, in the dark one:

    poetry run python docs/examples/mission.py
"""
import math
import random
from enum import IntEnum
from pathlib import Path

from matplotlib import pyplot as plt

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import StateMachine
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

ASSETS = Path(__file__).resolve().parent.parent / "assets"
# The suffix of each animation, and the matplotlib style it is drawn in: as it is, and dark.
THEMES = {"": {}, "-dark": Path(__file__).resolve().parent / "dark.mplstyle"}
SEED = 42  # the same lattice at every run, and in each theme
SIZE = 10  # drones on each side of the lattice
BASE = 0  # the drone next to the base, in a corner
TARGET = SIZE * SIZE - 1  # the drone that finds the target, in the opposite corner
SENSORS = ("base", "alarm", "attack", "safe", "found", "rescued")
# When each event happens, in rounds: an attack on the base while the target is found, so
# that the two transitions conflict, then the rescue, once the base is safe.
EVENTS = {
    3: {"alarm": True},
    12: {"attack": True, "found": True},
    22: {"attack": False, "safe": True},
    35: {"alarm": False, "rescued": True},
}
END = 42


# --8<-- [start:mission]
class Phase(IntEnum):
    """The phases of the mission: in a conflict of equal priority, the later one wins."""

    WAIT = 0
    EXPLORE = 1
    RESCUE = 2
    DEFEND = 3


mission = StateMachine(*Phase)


@mission.state(Phase.WAIT, to=[Phase.EXPLORE, Phase.DEFEND])
def wait() -> float:
    """Stay at the base, until an alarm or an attack."""
    if sense("attack"):
        mission.go(Phase.DEFEND, priority=math.inf)
    elif sense("alarm"):
        mission.go(Phase.EXPLORE)
    return distance_to(sense("base"), neighbors_distances())


@mission.state(Phase.EXPLORE, to=[Phase.RESCUE, Phase.DEFEND])
def explore() -> None:
    """Search the area, until a drone finds the target or the base is attacked."""
    if sense("attack"):
        mission.go(Phase.DEFEND, priority=math.inf)
    elif sense("found"):
        mission.go(Phase.RESCUE)


@mission.state(Phase.RESCUE, to=[Phase.WAIT])
def rescue() -> float:
    """Head for the target, until it is rescued."""
    if sense("rescued"):
        mission.go(Phase.WAIT)
    return distance_to(sense("found"), neighbors_distances())


@mission.state(Phase.DEFEND, to=[Phase.WAIT])
def defend() -> float:
    """Head for the base, until it is safe."""
    if sense("safe"):
        mission.go(Phase.WAIT)
    return distance_to(sense("base"), neighbors_distances())


@aggregate
def drone() -> Phase:
    """The program every drone runs: the phase it agrees on, and how far it has to go."""
    phase, distance = mission.run()
    store("distance", distance)
    return phase
# --8<-- [end:mission]


def sense_events(simulator: Simulator, events: dict[str, bool]) -> None:
    """The base or the target changes what it senses."""
    for sensor, value in events.items():
        drone = TARGET if sensor in ("found", "rescued") else BASE
        simulator.environment.nodes[drone].data[sensor] = value


def scene() -> Simulator:
    """The lattice of drones running the mission, with its events scheduled."""
    random.seed(SEED)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.2)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({sensor: False for sensor in SENSORS})
    simulator.environment.nodes[BASE].data["base"] = True
    schedule_program_for_all(simulator, 0.0, 1.0, drone)
    for time, events in EVENTS.items():
        simulator.schedule_event(time - 0.5, sense_events, simulator, events)
    return simulator


def record(simulator: Simulator, name: str) -> None:
    """Save the evolution of the phase to ``docs/assets/<name>``, a colour for each phase."""
    # Between 0 and 9, the ten colours of tab10 go one to each integer: blue, orange, green, red.
    effects = [
        DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap="tab10", vmin=0.0, vmax=9.0)
    ]
    config = RenderConfig(
        effects=effects, dt=1.0, mode=RenderMode.SAVE, save_as=str(ASSETS / name),
        show_axis=False, title="Collective state machine",
    )
    RenderMonitor(simulator, config)


def main() -> None:
    """Regenerate the animation of the mission, in both themes."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix, style in THEMES.items():
        with plt.style.context(style):
            simulator = scene()
            record(simulator, f"state-machine{suffix}.gif")
            simulator.run(END)


if __name__ == "__main__":
    main()

"""
A swarm of drones takes one shape after another: a star, a ring, then two crossed strokes.

Each drone knows where it is, and spreads evenly over the shape with its neighbors; the
shape changes in time, and the swarm follows. Run it to regenerate the animation in
``docs/assets``, in the light theme of the docs and, with ``-dark`` in its name, in the
dark one (smaller if ``gifsicle`` is on the PATH):

    poetry run python docs/examples/formation.py
"""
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

from matplotlib import pyplot as plt
from pydantic import ConfigDict

from phyelds.calculus import aggregate
from phyelds.experimental.formation import Shape, circle, formation, segment, star
from phyelds.libraries.device import store
from phyelds.libraries.time import local_time
from phyelds.simulator import Environment, Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.effects import DrawEdges, DrawNodes, Effect, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import adaptive_range
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

ASSETS = Path(__file__).resolve().parent.parent / "assets"
THEMES = {"": {}, "-dark": Path(__file__).resolve().parent / "dark.mplstyle"}
SEED = 7
DRONES = 40
RANGE = 3.0  # the communication range a drone starts with, adapted to keep about 12 neighbors
SPEED = 0.6  # the top speed of a drone, per time unit
LIMITS = (-10.0, 10.0)
END = 300

# --8<-- [start:formation]
SHAPES = [
    (0, star((0, 0), 8, 5)),
    (100, circle((0, 0), 7).ring(2)),
    (200, (segment((-6, -6), (6, 6)) | segment((-6, 6), (6, -6))).expand(1.5)),
]


def shape_at(time: float) -> Shape:
    """The shape the swarm takes at ``time``: the last one started."""
    return [shape for start, shape in SHAPES if start <= time][-1]


@aggregate
def drone() -> None:
    """The program every drone runs: where to move, to spread over the current shape."""
    store("velocity", formation(shape_at(local_time()), reach=RANGE / 2))
# --8<-- [end:formation]


class DrawShape(Effect):
    """Draw the shape of the moment, filled, under the drones."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    type: Literal["DrawShape"] = "DrawShape"
    shape_at: Any
    z_order: int = -1

    def apply(self, ax, environment: Environment):
        time = max((node.data.get("time", 0.0) for node in environment.nodes.values()), default=0.0)
        shape = self.shape_at(time)
        steps = [LIMITS[0] + (LIMITS[1] - LIMITS[0]) * index / 120 for index in range(121)]
        values = [[shape((x, y)) for x in steps] for y in steps]
        ax.contourf(steps, steps, values, levels=[-100, 0], colors=["tab:blue"], alpha=0.15)
        ax.set_aspect("equal")


def scene() -> Simulator:
    """The drones, scattered over the area, spreading over the shapes as they change."""
    random.seed(SEED)
    simulator = Simulator()
    for node_id in range(DRONES):
        simulator.create_node((random.uniform(*LIMITS), random.uniform(*LIMITS)), node_id=node_id)
    simulator.environment.set_neighborhood_function(
        adaptive_range(RANGE, neighbors=12, tolerance=6, step=0.1, min_range=1.0, max_range=6.0)
    )
    simulator.environment.add_data_for_all_nodes({"color": "tab:orange"})
    schedule_program_for_all(simulator, 0.0, 1.0, drone)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=SPEED)
    return simulator


def record(simulator: Simulator, name: str) -> None:
    """Save the run to ``docs/assets/<name>``."""
    config = RenderConfig(
        effects=[DrawShape(shape_at=shape_at), DrawEdges(alpha=0.2), DrawNodes(color_from="color")],
        dt=3.0, fps=10, mode=RenderMode.SAVE, save_as=str(ASSETS / name), xlim=LIMITS, ylim=LIMITS,
        show_axis=False, title="Formation on a signed distance function",
    )
    RenderMonitor(simulator, config)


def main() -> None:
    """Regenerate the animation of the formation, in both themes."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix, style in THEMES.items():
        with plt.style.context(style):
            simulator = scene()
            record(simulator, f"formation{suffix}.gif")
            simulator.run(END)
        if shutil.which("gifsicle"):
            gif = str(ASSETS / f"formation{suffix}.gif")
            subprocess.run(["gifsicle", "-O3", "--colors", "64", "--batch", gif], check=True)


if __name__ == "__main__":
    main()

"""
The animations of the library pages: leader clusters, a process bubble and a corridor.

They run the programs of the playground examples, on the larger scenes the pages show,
and the corridor that the tutorial builds.
Run it to regenerate them in ``docs/assets``, each in the light theme of the docs and,
with ``-dark`` in its name, in the dark one:

    poetry run python docs/examples/animations.py
"""
import importlib.util
import random
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

from matplotlib import pyplot as plt

from phyelds.calculus import aggregate
from phyelds.libraries.collect import collect_or
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PLAYGROUND = Path(__file__).resolve().parent / "playground"
ROUND = 0.5  # time between two rounds of a device, and between two frames
SEED = 42  # the same lattices at every run, and in each theme
# The suffix of each animation, and the matplotlib style it is drawn in: as it is, and dark.
THEMES = {"": {}, "-dark": Path(__file__).resolve().parent / "dark.mplstyle"}
WIDTH = 1.6  # devices one apart: a corridor a device or so wide on each side of the path


def example(name: str) -> ModuleType:
    """The playground example ``name``, as a module of its own."""
    spec = importlib.util.spec_from_file_location(f"{name}_example", PLAYGROUND / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deploy(size: int, deformation: float, sensors: Iterable[str] = ()) -> Simulator:
    """A deformed lattice of ``size`` x ``size`` devices one apart, hearing within 1.5, its ``sensors`` off."""
    random.seed(SEED)
    simulator = Simulator()
    deformed_lattice(simulator, size, size, spacing=1.0, deformation_factor=deformation)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({name: False for name in sensors})
    return simulator


def record(simulator: Simulator, name: str, title: str, cmap: str, vmax: float) -> None:
    """Save the evolution of the result to ``docs/assets/<name>``, its colours fixed between 0 and ``vmax``."""
    effects = [DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap=cmap, vmin=0.0, vmax=vmax)]
    config = RenderConfig(
        effects=effects, dt=ROUND, mode=RenderMode.SAVE, save_as=str(ASSETS / name), show_axis=False, title=title
    )
    RenderMonitor(simulator, config)


def leaders(save: bool = True, suffix: str = "") -> Simulator:
    """Leaders elected sparsely over a 10x10 lattice, each the centre of a cluster."""
    program = example("leaders")
    # The playground's arena is 5 wide: on a lattice twice as large, the leaders lie farther apart.
    program.GRAIN = 4.5
    simulator = deploy(10, deformation=0.25)
    if save:
        record(simulator, f"leaders{suffix}.gif", "Leader clusters", "tab20", vmax=99.0)
    schedule_program_for_all(simulator, 0.0, ROUND, program.cluster_id)
    simulator.run(16 * ROUND)
    return simulator


def clear_alarm(simulator: Simulator, node_id: int) -> None:
    """The alarm of ``node_id`` stops, and its bubble is cleared."""
    simulator.environment.nodes[node_id].data.update({"alarm": False, "clear": True})


def bubbles(save: bool = True, suffix: str = "") -> Simulator:
    """A process bubble spawned by an alarm in the middle of a 9x9 lattice, then shut down."""
    program = example("bubbles")
    program.MAX_HOPS = 3.0  # on the larger lattice, the bubble reaches farther
    origin = 40  # the device in the middle
    simulator = deploy(9, deformation=0.2, sensors=["alarm", "clear"])
    simulator.environment.nodes[origin].data["alarm"] = True
    if save:
        record(simulator, f"bubbles{suffix}.gif", "Process bubble", "magma", vmax=program.MAX_HOPS + 1.0)
    schedule_program_for_all(simulator, 0.0, ROUND, program.monitor_alerts)
    simulator.schedule_event(8 * ROUND + ROUND / 2, clear_alarm, simulator, origin)
    simulator.run(16 * ROUND)
    return simulator


@aggregate
def corridor_program() -> float:
    """1.0 on the devices within WIDTH of the shortest path from the source to the target, 0.0 elsewhere."""
    distances = neighbors_distances()
    to_target = distance_to(sense("target"), distances)
    on_path = collect_or(to_target, sense("source"))
    return 1.0 if distance_to(on_path, distances) < WIDTH else 0.0


def corridor(save: bool = True, suffix: str = "") -> Simulator:
    """The corridor between two opposite corners of a 12x12 lattice."""
    simulator = deploy(12, deformation=0.25, sensors=["source", "target"])
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[12 * 12 - 1].data["target"] = True
    if save:
        record(simulator, f"channel{suffix}.gif", "Channel", "plasma", vmax=1.0)
    schedule_program_for_all(simulator, 0.0, ROUND, corridor_program)
    simulator.run(25 * ROUND)
    return simulator


def main() -> None:
    """Regenerate the animations of the library pages, in both themes."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix, style in THEMES.items():
        with plt.style.context(style):
            leaders(suffix=suffix)
            bubbles(suffix=suffix)
            corridor(suffix=suffix)


if __name__ == "__main__":
    main()

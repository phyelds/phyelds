"""
The gradient, step by step: the programs and scenes shown in the README.

Run it to regenerate the animations in ``docs/assets``:

    poetry run python docs/examples/gradient.py
"""
import random
from pathlib import Path

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice, grid_generation
from phyelds.simulator.effects import (
    DrawEdges,
    DrawNodes,
    DrawValues,
    RenderConfig,
    RenderMode,
)
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

ASSETS = Path(__file__).resolve().parent.parent / "assets"
INFINITY = float("inf")
ROUND = 0.5  # time between two rounds of a device, and between two frames
LATTICE_DIAMETER = 16.0  # about the distance between opposite corners of a 12x12 lattice


@aggregate
def hop_gradient(source: bool) -> float:
    """Number of hops to the nearest source, built from remember and neighbors."""
    set_distance, distance = remember(INFINITY)
    through_neighbors = neighbors(distance) + 1
    nearest = min(through_neighbors.exclude_self().values(), default=INFINITY)
    set_distance(0 if source else nearest)
    return distance


@aggregate
def hop_gradient_program() -> float:
    """The program every device runs: a hop gradient from the `source` sensor."""
    return hop_gradient(sense("source"))


@aggregate
def metric_gradient_program() -> float:
    """The same field, with the library gradient and real distances between devices."""
    return distance_to(sense("source"), neighbors_distances())


def deploy_grid(
    width: int, height: int, deformation: float = 0.0, radius: float = 1.1
) -> Simulator:
    """Create a simulator with a (possibly deformed) grid of devices, no source."""
    simulator = Simulator()
    if deformation:
        deformed_lattice(simulator, width, height, spacing=1.0, deformation_factor=deformation)
    else:
        grid_generation(simulator, width, height, spacing=1.0)
    simulator.environment.set_neighborhood_function(radius_neighborhood(radius))
    simulator.environment.add_data_for_all_nodes({"source": False})
    return simulator


def set_source(simulator: Simulator, node_id: int) -> None:
    """Make a device a source."""
    simulator.environment.nodes[node_id].data["source"] = True


def move_source(simulator: Simulator, old: int, new: int) -> None:
    """Turn the source `old` into a normal device and make `new` the source."""
    simulator.environment.nodes[old].data["source"] = False
    set_source(simulator, new)


def record(
    simulator: Simulator, name: str, vmax: float, labels: bool = False, **options
) -> None:
    """
    Attach a monitor that saves the evolution of the field to ``docs/assets/<name>``.
    The colour scale is fixed between 0 and ``vmax``, so a colour means the same
    distance in every frame; ``labels`` also writes each value next to its device.
    The other ``options`` (e.g. ``title``, ``xlim``) go to ``RenderConfig``.
    """
    effects = [
        DrawEdges(alpha=0.3),
        DrawNodes(color_from="result", cmap="viridis_r", vmin=0.0, vmax=vmax),
    ]
    if labels:
        effects.append(DrawValues(value_from="result", precision=1))
    config = RenderConfig(
        effects=effects,
        dt=ROUND,
        mode=RenderMode.SAVE,
        save_as=str(ASSETS / name),
        show_axis=False,
        **options,
    )
    RenderMonitor(simulator, config)


def hops_on_a_line() -> None:
    """A wave of hop counts that leaves the source and crosses the line."""
    simulator = deploy_grid(width=10, height=1)
    set_source(simulator, 0)
    record(
        simulator,
        "gradient-hops.gif",
        vmax=9,
        labels=True,
        title="Hop-count gradient",
        xlim=(-0.5, 9.5),
        ylim=(-2.0, 2.0),
    )
    schedule_program_for_all(simulator, 0.0, ROUND, hop_gradient_program)
    simulator.run(12 * ROUND)


def distances_on_a_lattice() -> None:
    """The metric gradient on an irregular network."""
    simulator = deploy_grid(width=12, height=12, deformation=0.25, radius=1.5)
    set_source(simulator, 0)
    record(simulator, "gradient-distance.gif", LATTICE_DIAMETER, title="Distance gradient")
    schedule_program_for_all(simulator, 0.0, ROUND, metric_gradient_program)
    simulator.run(25 * ROUND)


def self_healing() -> None:
    """The source jumps to the opposite corner: the field repairs itself."""
    simulator = deploy_grid(width=12, height=12, deformation=0.25, radius=1.5)
    set_source(simulator, 0)
    record(
        simulator, "gradient-self-healing.gif", LATTICE_DIAMETER, title="Self-healing gradient"
    )
    schedule_program_for_all(simulator, 0.0, ROUND, metric_gradient_program)
    last = len(simulator.environment.nodes) - 1
    simulator.schedule_event(20 * ROUND + ROUND / 2, move_source, simulator, 0, last)
    simulator.run(50 * ROUND)


def main() -> None:
    """Regenerate every animation used by the README."""
    random.seed(42)
    ASSETS.mkdir(parents=True, exist_ok=True)
    hops_on_a_line()
    distances_on_a_lattice()
    self_healing()


if __name__ == "__main__":
    main()

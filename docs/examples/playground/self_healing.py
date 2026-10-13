"""
Self-healing: the source jumps to the opposite corner and the gradient repairs itself.

Nobody tells the devices that the source moved: they find out from their neighbours.
"""
import random

from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

SIZE = 10  # devices on each side of the lattice
ROUND = 0.5  # time between two rounds of a device, and between two frames
MOVE_AT = 15 * ROUND  # when the source jumps


@aggregate
def gradient() -> float:
    """The distance from the nearest device whose `source` sensor is on."""
    return distance_to(sense("source"), neighbors_distances())


def move_source(simulator: Simulator, old: int, new: int) -> None:
    """Switch off the source `old` and switch on `new`."""
    simulator.environment.nodes[old].data["source"] = False
    simulator.environment.nodes[new].data["source"] = True


def main() -> None:
    """Run the gradient, move its source halfway and save self_healing.gif."""
    random.seed(42)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.25)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({"source": False})
    first, last = 0, SIZE * SIZE - 1
    simulator.environment.nodes[first].data["source"] = True
    RenderMonitor(simulator, RenderConfig(
        effects=[DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap="plasma_r", vmin=0.0, vmax=SIZE * 1.4)],
        dt=ROUND, mode=RenderMode.SAVE, save_as="self_healing.gif", show_axis=False, title="Self-healing gradient",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, gradient)
    simulator.schedule_event(MOVE_AT + ROUND / 2, move_source, simulator, first, last)
    simulator.run(MOVE_AT + 20 * ROUND)

    at_old_source = simulator.environment.nodes[first].data["result"]
    print(f"The old source is now {at_old_source:.1f} away from the new one")


if __name__ == "__main__":
    main()

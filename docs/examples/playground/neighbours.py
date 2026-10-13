"""
Neighbours: every device counts the devices within its communication range.

Change RADIUS and run again: the same program gives a different field.
"""
import random

from phyelds.calculus import aggregate, neighbors
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, DrawValues, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

SIZE = 7  # devices on each side of the lattice
RADIUS = 1.5  # communication range of every device
ROUND = 1.0  # time between two rounds of a device


@aggregate
def neighbour_count() -> int:
    """How many devices this device hears, itself excluded."""
    return len(neighbors(1).exclude_self())


def main() -> None:
    """Scatter the devices on a lattice, run three rounds and save neighbours.gif."""
    random.seed(1)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.45)
    simulator.environment.set_neighborhood_function(radius_neighborhood(RADIUS))
    RenderMonitor(simulator, RenderConfig(
        effects=[DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap="plasma"), DrawValues(value_from="result")],
        dt=ROUND, mode=RenderMode.SAVE, save_as="neighbours.gif", show_axis=False, title="Neighbour count",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, neighbour_count)
    simulator.run(3 * ROUND)

    counts = [node.data["result"] for node in simulator.environment.nodes.values()]
    print(f"{SIZE * SIZE} devices, from {min(counts)} to {max(counts)} neighbours each")


if __name__ == "__main__":
    main()

"""
Gradient: every device estimates its distance from the nearest source.

The field grows from the source, one round at a time, through neighbours only.
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
SOURCE = 0  # the device in the bottom-left corner
ROUND = 0.5  # time between two rounds of a device, and between two frames


@aggregate
def gradient() -> float:
    """The distance from the nearest device whose `source` sensor is on."""
    return distance_to(sense("source"), neighbors_distances())


def main() -> None:
    """Run the gradient on a lattice and save gradient.gif."""
    random.seed(42)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.25)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({"source": False})
    simulator.environment.nodes[SOURCE].data["source"] = True
    RenderMonitor(simulator, RenderConfig(
        effects=[DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap="plasma_r", vmin=0.0, vmax=SIZE * 1.4)],
        dt=ROUND, mode=RenderMode.SAVE, save_as="gradient.gif", show_axis=False, title="Distance gradient",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, gradient)
    simulator.run(20 * ROUND)

    farthest = max(node.data["result"] for node in simulator.environment.nodes.values())
    print(f"The farthest device is {farthest:.1f} away from the source")


if __name__ == "__main__":
    main()

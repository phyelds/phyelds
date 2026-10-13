"""
Channel: the devices between a source and a target form a band along the shortest path.

It combines two gradients and a collection: try changing WIDTH.
"""
import random

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

SIZE = 12  # devices on each side of the lattice
WIDTH = 1.6  # how far from the path a device still belongs to the channel
ROUND = 0.5  # time between two rounds of a device, and between two frames


@aggregate
def channel() -> float:
    """1.0 on the devices close to the path from the source to the target, 0.0 elsewhere."""
    distances = neighbors_distances()
    to_target = distance_to(sense("target"), distances)
    on_path = collect_or(to_target, sense("source"))
    return 1.0 if distance_to(on_path, distances) < WIDTH else 0.0


def main() -> None:
    """Run the channel between two opposite corners and save channel.gif."""
    random.seed(42)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.25)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({"source": False, "target": False})
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[SIZE * SIZE - 1].data["target"] = True
    RenderMonitor(simulator, RenderConfig(
        effects=[DrawEdges(alpha=0.3), DrawNodes(color_from="result", cmap="plasma", vmin=0.0, vmax=1.0)],
        dt=ROUND, mode=RenderMode.SAVE, save_as="channel.gif", show_axis=False, title="Channel",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, channel)
    simulator.run(25 * ROUND)

    in_channel = sum(node.data["result"] for node in simulator.environment.nodes.values())
    print(f"{in_channel:.0f} of {SIZE * SIZE} devices form the channel")


if __name__ == "__main__":
    main()

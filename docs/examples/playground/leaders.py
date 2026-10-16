"""
Leaders: the network elects sparse leaders and partitions itself into Voronoi clusters.

Change GRAIN to control the radius of each cluster and how many leaders emerge.
"""
import random

from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import candidacy, elect_leaders
from phyelds.libraries.spreading import broadcast
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

SIZE = 10  # devices on each side of the lattice
GRAIN = 4.5  # minimum distance between elected leaders
ROUND = 0.5  # time between two rounds of a device, and between two frames


@aggregate
def cluster_id() -> float:
    """Elect sparse leaders and broadcast each leader's ID across its Voronoi region."""
    distances = neighbors_distances()
    is_leader = elect_leaders(GRAIN, distances, strategy=candidacy())
    return float(broadcast(is_leader, local_id(), distances))


def main() -> None:
    """Partition the lattice around elected leaders and save leaders.gif."""
    random.seed(42)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.25)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    RenderMonitor(simulator, RenderConfig(
        effects=[
            DrawEdges(alpha=0.3),
            DrawNodes(color_from="result", cmap="tab20", vmin=0.0, vmax=float(SIZE * SIZE - 1)),
        ],
        dt=ROUND, mode=RenderMode.SAVE, save_as="leaders.gif", show_axis=False, title="Leader clusters",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, cluster_id)
    simulator.run(16 * ROUND)

    clusters = {int(node.data["result"]) for node in simulator.environment.nodes.values()}
    print(f"Elected {len(clusters)} leaders: {sorted(clusters)}")


if __name__ == "__main__":
    main()

"""
Bubbles: an aggregate process spawns on an alert, expands up to a radius, and shuts down.

Change MAX_HOPS to control how far the process bubble spreads from its origin.
"""
import random

from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.processes import in_bubble, process, terminate_if
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import deformed_lattice
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.render import RenderMonitor
from phyelds.simulator.runner import schedule_program_for_all

SIZE = 9  # devices on each side of the lattice
ORIGIN = 40  # the center device where the alert starts
MAX_HOPS = 3.0  # spatial radius of the process bubble
ROUND = 0.5  # time between two rounds of a device, and between two frames


@process
def alert_bubble(origin: int) -> float:
    """Expand up to MAX_HOPS from `origin` and shut down when the origin clears."""
    is_origin = local_id() == origin
    hops = float(distance_to(is_origin))
    terminate_if(is_origin and sense("clear"))
    in_bubble(hops <= MAX_HOPS)
    return MAX_HOPS - hops + 1.0


@aggregate
def monitor_alerts() -> float:
    """Spawn an alert bubble when `alarm` is sensed; return 0.0 outside the bubble."""
    keys = {local_id()} if sense("alarm") else set()
    active = alert_bubble.spawn(keys)
    return max(active.values(), default=0.0)


def clear_alarm(simulator: Simulator, node_id: int) -> None:
    """Stop spawning new alerts and trigger the termination wave."""
    simulator.environment.nodes[node_id].data["alarm"] = False
    simulator.environment.nodes[node_id].data["clear"] = True


def main() -> None:
    """Spawn a bubble at the center, let it expand, then terminate it and save bubbles.gif."""
    random.seed(42)
    simulator = Simulator()
    deformed_lattice(simulator, SIZE, SIZE, spacing=1.0, deformation_factor=0.2)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({"alarm": False, "clear": False})
    simulator.environment.nodes[ORIGIN].data["alarm"] = True
    RenderMonitor(simulator, RenderConfig(
        effects=[
            DrawEdges(alpha=0.3),
            DrawNodes(color_from="result", cmap="magma", vmin=0.0, vmax=MAX_HOPS + 1.0),
        ],
        dt=ROUND, mode=RenderMode.SAVE, save_as="bubbles.gif", show_axis=False, title="Process bubble",
    ))
    schedule_program_for_all(simulator, 0.0, ROUND, monitor_alerts)
    simulator.schedule_event(8 * ROUND + ROUND / 2, clear_alarm, simulator, ORIGIN)
    simulator.run(16 * ROUND)

    inside = sum(1 for node in simulator.environment.nodes.values() if node.data["result"] > 0.0)
    print(f"Active devices remaining after termination: {inside}")


if __name__ == "__main__":
    main()

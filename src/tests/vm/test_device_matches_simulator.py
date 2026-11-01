"""
The simulator and a loop of ``Device``s, on the same topology and schedule, run the same
rounds: a program computes the same results in each round, whatever the wire format.
"""
import random

import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import aggregate_program_runner
from phyelds.vm.device import Device

ROUNDS = 12


@aggregate
def gradient_leader_count():
    potential = distance_to(sense("source"))
    return potential.value, gossip_max(local_id()).value, count_nodes(potential).value


def _grid_with_phases() -> tuple[Simulator, dict[int, float]]:
    """A 4×3 grid where each node reaches the 8 around it, and when in each period a node runs."""
    simulator = Simulator()
    grid_generation(simulator, 4, 3, spacing=1)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.5))
    simulator.environment.add_data_for_all_nodes({"source": False})
    simulator.environment.nodes[0].data["source"] = True
    order = sorted(simulator.environment.nodes)
    random.Random(7).shuffle(order)
    phases = {node_id: (rank + 1) / (len(order) + 1) for rank, node_id in enumerate(order)}
    return simulator, phases


def _simulator_rounds(simulator: Simulator, phases: dict[int, float]) -> list[dict]:
    for node in simulator.environment.node_list():
        simulator.schedule_event(
            phases[node.id], aggregate_program_runner, simulator, 1.0, node, gradient_leader_count
        )
    rounds = []
    for end in range(1, ROUNDS + 1):
        simulator.run(until_time=end)
        rounds.append({node.id: node.data["result"] for node in simulator.environment.node_list()})
    return rounds


def _device_rounds(simulator: Simulator, phases: dict[int, float], **options) -> list[dict]:
    """The same rounds on Devices: each one sends its bytes to its neighbors right after its round."""
    environment = simulator.environment
    devices = {node_id: Device(node_id, gradient_leader_count, **options) for node_id in environment.nodes}
    neighbors = {node.id: [other.id for other in environment.get_neighbors(node)] for node in environment.node_list()}
    rounds = []
    for _ in range(ROUNDS):
        for node_id in sorted(phases, key=phases.get):
            device = devices[node_id]
            payload = device.run_round({"source": environment.nodes[node_id].data["source"]})
            for neighbor, addressed in device.addressed.items():  # the addressed ones first
                devices[neighbor].receive(node_id, addressed)
            for neighbor in neighbors[node_id]:
                devices[neighbor].receive(node_id, payload)
        rounds.append({node_id: device.result for node_id, device in devices.items()})
    return rounds


@pytest.mark.parametrize("options", [
    {},
    {"paths": "compact", "binary": True},
    {"paths": "compact", "binary": True, "messages": "addressed"},
])
def test_device_computes_the_rounds_of_the_simulator_on_the_same_topology_and_schedule(options):
    simulator, phases = _grid_with_phases()

    expected = _simulator_rounds(simulator, phases)
    actual = _device_rounds(simulator, phases, **options)

    assert actual == expected

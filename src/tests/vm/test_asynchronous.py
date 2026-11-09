"""
The asynchronous runtime and the simulator, on the same topology and schedule, run the same
rounds: each device sends right after its own round.
"""
import random

import pytest

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import aggregate_program_runner
from phyelds.vm.asynchronous import AsynchronousRuntime

ROUNDS = 12


@aggregate
def gradient_leader_count():
    potential = distance_to(sense("source"))
    return potential, gossip_max(local_id()), count_nodes(potential)


@aggregate
def rounds():
    set_count, count = remember(0)
    return set_count(count + 1)


@aggregate
def neighbor_count():
    count = neighbors(1).sum(include_self=False)
    store("neighbors", count)
    return count


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


def test_asynchronous_runtime_computes_the_rounds_of_the_simulator_on_the_same_schedule():
    simulator, phases = _grid_with_phases()
    environment = simulator.environment
    order = sorted(phases, key=phases.get)
    neighbors = {
        node.id: [other.id for other in environment.get_neighbors(node)]
        for node in environment.node_list()
    }
    sensors = {device: {"source": device == 0} for device in order}
    runtime = AsynchronousRuntime(gradient_leader_count)

    expected = _simulator_rounds(simulator, phases)
    actual = [runtime.run_round(sensors, neighbors) for _ in range(ROUNDS)]

    assert actual == expected


def test_asynchronous_runtime_keeps_the_state_of_each_device_across_rounds_until_reset():
    topology = {0: [1], 1: [0]}
    sensors = {0: {}, 1: {}}
    runtime = AsynchronousRuntime(rounds)
    for _ in range(3):
        runtime.run_round(sensors, topology)

    runtime.reset()

    assert runtime.run_round(sensors, topology) == {0: 1, 1: 1}


def test_asynchronous_runtime_spikes_one_device_without_forgetting_the_others():
    runtime = AsynchronousRuntime(rounds)
    runtime.spike(0, {}, [1])
    runtime.spike(1, {}, [0])

    assert runtime.spike(0, {}, [1]) == 2
    assert runtime.spike(0, {}, [1]) == 3
    assert runtime.spike(1, {}, [0]) == 2


def test_asynchronous_runtime_exposes_what_the_program_stored():
    topology = {0: [1, 2], 1: [0], 2: [0]}
    sensors = {0: {}, 1: {}, 2: {}}
    runtime = AsynchronousRuntime(neighbor_count)

    for _ in range(2):
        runtime.run_round(sensors, topology)

    assert runtime.outputs == {0: {"neighbors": 2}, 1: {"neighbors": 1}, 2: {"neighbors": 1}}


def test_asynchronous_runtime_forgets_the_state_messages_and_outputs_of_a_device():
    topology = {0: [1], 1: [0]}
    sensors = {0: {}, 1: {}}
    runtime = AsynchronousRuntime(neighbor_count)
    for _ in range(2):
        runtime.run_round(sensors, topology)
    counted = AsynchronousRuntime(rounds)
    for _ in range(3):
        counted.run_round(sensors, topology)

    runtime.forget(1)
    counted.forget(1)

    assert runtime.outputs == {0: {"neighbors": 1}}
    assert runtime.spike(0, {}, [1]) == 0
    assert counted.spike(1, {}, [0]) == 1


def test_asynchronous_runtime_forgets_a_device_silent_for_longer_than_the_retention_time():
    runtime = AsynchronousRuntime(neighbor_count, retention=2.0)
    runtime.spike(1, {"time": 0.0}, [0])

    assert runtime.spike(0, {"time": 2.0}, [1]) == 1
    assert runtime.spike(0, {"time": 2.5}, [1]) == 0
    assert 1 not in runtime.outputs


def test_asynchronous_runtime_accepts_the_time_as_an_argument_of_spike_and_run_round():
    runtime = AsynchronousRuntime(neighbor_count, retention=2.0)
    runtime.spike(1, {}, [0], time=0.0)

    assert runtime.run_round({0: {}}, {0: [1]}, time=2.0) == {0: 1}
    assert runtime.run_round({0: {}}, {0: [1]}, time=2.5) == {0: 0}


def test_asynchronous_runtime_rejects_a_non_positive_retention_time():
    with pytest.raises(ValueError, match="positive"):
        AsynchronousRuntime(rounds, retention=0)


def test_asynchronous_runtime_requires_a_time_when_retention_is_set():
    runtime = AsynchronousRuntime(rounds, retention=1.0)

    with pytest.raises(ValueError, match="time"):
        runtime.spike(0, {}, [])

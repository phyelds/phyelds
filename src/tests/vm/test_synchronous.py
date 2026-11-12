"""
The synchronous runtime and a loop of ``Device``s, on the same topology, run the same rounds:
every device runs, and then every device sends.
"""
import pytest

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.vm.device import Device
from phyelds.vm.synchronous import SynchronousRuntime

ROUNDS = 12


@aggregate
def gradient_leader_count():
    potential = distance_to(sense("source"))
    return potential, gossip_max(local_id()), count_nodes(potential)


@aggregate
def rounds():
    count, set_count = remember(0)
    return set_count(count + 1)


@aggregate
def neighbor_count():
    count = neighbors(1).sum(include_self=False)
    store("neighbors", count)
    return count


def _grid(width: int, height: int) -> dict[int, list[int]]:
    """The devices of a grid, x * height + y, each one reaching the 8 around it."""
    return {
        x * height + y: [
            other_x * height + other_y
            for other_x in range(max(0, x - 1), min(width, x + 2))
            for other_y in range(max(0, y - 1), min(height, y + 2))
            if (other_x, other_y) != (x, y)
        ]
        for x in range(width) for y in range(height)
    }


def _sensors(topology: dict[int, list[int]]) -> dict[int, dict[str, bool]]:
    return {device: {"source": device == 0} for device in topology}


def _device_rounds(topology: dict[int, list[int]]) -> list[dict]:
    devices = {device: Device(device, gradient_leader_count) for device in topology}
    sensors = _sensors(topology)
    rounds = []
    for _ in range(ROUNDS):
        sent = {device: devices[device].run_round(sensors[device]) for device in topology}
        for device, others in topology.items():
            for other in others:
                devices[other].receive(device, sent[device])
        rounds.append({device: devices[device].result for device in topology})
    return rounds


def test_synchronous_runtime_computes_the_rounds_of_devices_on_the_same_topology():
    topology = _grid(4, 3)
    runtime = SynchronousRuntime(gradient_leader_count)

    expected = _device_rounds(topology)
    actual = [runtime.run_round(_sensors(topology), topology) for _ in range(ROUNDS)]

    assert actual == expected


def test_synchronous_runtime_keeps_the_state_of_each_device_across_rounds_until_reset():
    topology = {0: [1], 1: [0]}
    runtime = SynchronousRuntime(rounds)
    for _ in range(3):
        runtime.run_round(_sensors(topology), topology)

    runtime.reset()

    assert runtime.run_round(_sensors(topology), topology) == {0: 1, 1: 1}


def test_synchronous_runtime_exposes_what_the_program_stored():
    topology = {0: [1, 2], 1: [0], 2: [0]}
    runtime = SynchronousRuntime(neighbor_count)

    for _ in range(2):
        runtime.run_round(_sensors(topology), topology)

    assert runtime.outputs == {0: {"neighbors": 2}, 1: {"neighbors": 1}, 2: {"neighbors": 1}}


def test_synchronous_runtime_forgets_the_devices_missing_from_a_round():
    runtime = SynchronousRuntime(rounds)
    topology = {0: [1], 1: [0]}
    for _ in range(3):
        runtime.run_round(_sensors(topology), topology)

    alone = {0: []}
    runtime.run_round(_sensors(alone), alone)
    results = runtime.run_round(_sensors(topology), topology)

    assert results == {0: 5, 1: 1}


@pytest.mark.parametrize("program", [gradient_leader_count, neighbor_count])
def test_synchronous_runtime_computes_the_same_rounds_in_worker_threads(program):
    topology = _grid(7, 5)
    sequential = SynchronousRuntime(program)
    threaded = SynchronousRuntime(program, workers=4)

    expected = [sequential.run_round(_sensors(topology), topology) for _ in range(ROUNDS)]
    actual = [threaded.run_round(_sensors(topology), topology) for _ in range(ROUNDS)]

    assert actual == expected
    assert list(actual[-1]) == list(expected[-1])
    assert threaded.outputs == sequential.outputs


def test_synchronous_runtime_rejects_fewer_than_one_worker():
    with pytest.raises(ValueError, match="at least 1"):
        SynchronousRuntime(rounds, workers=0)


def test_synchronous_runtime_uses_compact_paths_by_default_and_accepts_engine_factory():
    topology = {0: [1], 1: [0]}
    calls = []

    def custom_factory():
        calls.append(1)
        return MutableEngine(paths="debug")

    from phyelds.vm.internal import MutableEngine  # pylint: disable=import-outside-toplevel

    default_runtime = SynchronousRuntime(neighbor_count)
    default_runtime.run_round(_sensors(topology), topology)
    assert all(isinstance(key, int) for outbox in default_runtime._outboxes.values() for key in outbox)  # pylint: disable=protected-access

    custom_runtime = SynchronousRuntime(neighbor_count, engine_factory=custom_factory)
    assert custom_runtime.run_round(_sensors(topology), topology) == {0: 0, 1: 0}
    assert custom_runtime.run_round(_sensors(topology), topology) == {0: 1, 1: 1}
    assert calls

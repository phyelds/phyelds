"""
The synchronous runtime and a loop of ``Device``s, on the same topology, run the same rounds:
every device runs, and then every device sends.
"""
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
    return potential.value, gossip_max(local_id()).value, count_nodes(potential).value


@aggregate
def rounds():
    set_count, count = remember(0)
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

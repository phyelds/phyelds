"""Differential round-by-round tests against the pure-Python runtimes and Device."""

import pytest

from phyelds.accel import AsynchronousRuntime as NativeAsyncRuntime
from phyelds.accel import SynchronousRuntime as NativeSyncRuntime
from phyelds.accel import run_round as native_run_round
from phyelds.calculus import aggregate, neighbors
from phyelds.data.codec import encode
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max, time_replicated_gossip
from phyelds.libraries.leader_election import candidacy, elect_leader
from phyelds.libraries.spreading import distance_to
from phyelds.vm.asynchronous import AsynchronousRuntime as PyAsyncRuntime
from phyelds.vm.device import Device
from phyelds.vm.synchronous import SynchronousRuntime as PySyncRuntime

ROUNDS = 14


@aggregate
def _benchmark_suite():
    potential = distance_to(sense("source"))
    leader = elect_leader(3.0, strategy=candidacy())
    replicated = gossip_max(local_id(), strategy=time_replicated_gossip(period=4.0))
    counted = count_nodes(potential)
    store("potential", potential)
    return potential, gossip_max(local_id()), counted, leader, replicated


@aggregate
def _neighbor_count():
    total = neighbors(1).sum(include_self=False)
    store("neighbors", total)
    return total


def _grid(width: int, height: int) -> dict[int, list[int]]:
    return {
        x * height + y: [
            ox * height + oy
            for ox in range(max(0, x - 1), min(width, x + 2))
            for oy in range(max(0, y - 1), min(height, y + 2))
            if (ox, oy) != (x, y)
        ]
        for x in range(width)
        for y in range(height)
    }


def _sensors(topology: dict[int, list[int]], step: int) -> dict[int, dict[str, object]]:
    return {
        device: {"source": device == 0, "time": float(step)}
        for device in topology
    }


def test_native_synchronous_runtime_matches_python_vm_in_every_round():
    topology = _grid(5, 4)
    py_runtime = PySyncRuntime(_benchmark_suite)
    c_runtime = NativeSyncRuntime(_benchmark_suite)

    for step in range(ROUNDS):
        sensors = _sensors(topology, step)
        assert c_runtime.run_round(sensors, topology) == py_runtime.run_round(sensors, topology)
        assert c_runtime.outputs == py_runtime.outputs


def test_native_synchronous_runtime_matches_across_worker_threads():
    topology = _grid(7, 5)
    single = NativeSyncRuntime(_benchmark_suite, workers=1)
    threaded = NativeSyncRuntime(_benchmark_suite, workers=4)

    for step in range(ROUNDS):
        sensors = _sensors(topology, step)
        assert threaded.run_round(sensors, topology) == single.run_round(sensors, topology)
        assert threaded.outputs == single.outputs
    threaded.close()
    single.close()


def test_native_synchronous_runtime_forgets_missing_devices_and_resets():
    topology = {0: [1], 1: [0]}
    runtime = NativeSyncRuntime(_neighbor_count)
    runtime.run_round({0: {}, 1: {}}, topology)
    assert runtime.run_round({0: {}, 1: {}}, topology) == {0: 1, 1: 1}

    assert runtime.run_round({0: {}}, {0: []}) == {0: 0}
    runtime.reset()
    assert runtime.outputs == {}
    with pytest.raises(ValueError, match="at least 1"):
        NativeSyncRuntime(_neighbor_count, workers=0)


def test_native_asynchronous_runtime_matches_python_vm_spikes_and_retention():
    topology = _grid(4, 3)
    py_runtime = PyAsyncRuntime(_benchmark_suite, retention=2.0)
    c_runtime = NativeAsyncRuntime(_benchmark_suite, retention=2.0)

    for step in range(ROUNDS):
        sensors = _sensors(topology, step)
        assert c_runtime.run_round(sensors, topology) == py_runtime.run_round(sensors, topology)
        assert c_runtime.outputs == py_runtime.outputs

    py_ret = PyAsyncRuntime(_neighbor_count, retention=2.0)
    c_ret = NativeAsyncRuntime(_neighbor_count, retention=2.0)
    for rt in (py_ret, c_ret):
        rt.spike(1, {}, [0], time=0.0)
    assert c_ret.spike(0, {}, [1], time=2.0) == py_ret.spike(0, {}, [1], time=2.0) == 1
    assert c_ret.spike(0, {}, [1], time=2.5) == py_ret.spike(0, {}, [1], time=2.5) == 0
    assert c_ret.outputs == py_ret.outputs

    no_retention = NativeAsyncRuntime(_neighbor_count)
    assert no_retention.spike(0, {}, [1]) == 0
    with pytest.raises(ValueError, match="time"):
        c_ret.spike(0, {}, [1])


def test_native_outbox_interoperates_with_device_over_binary_wire_codec():
    device = Device(1, _neighbor_count, paths="compact", binary=True)
    done = native_run_round(_neighbor_count, 0, {}, {})
    device.receive(0, encode(done.outbox, binary=True))

    payload = device.run_round({})
    assert device.result == 1
    assert payload

"""Round-by-round equivalence tests of unchanged @aggregate programs on CPU/CUDA vs Python VM."""

import math
import random

import pytest
import torch

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.gpu import GpuSynchronousRuntime
from phyelds.libraries.collect import collect_or, count_nodes, mean_values, sum_values
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.gossip import any_node, gossip_max, gossip_mean, gossip_min
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import (
    counter,
    decay,
    delay,
    delta_time,
    exponential_filter,
    falling_edge,
    rising_edge,
    shared_clock,
    timer,
)
from phyelds.vm.synchronous import SynchronousRuntime

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]


@aggregate
def _core_benchmarks():
    pot = distance_to(sense("source"))
    return pot, gossip_max(local_id()), gossip_min(local_id()), count_nodes(pot)


@aggregate
def _metric_gradient_and_collect():
    dists = neighbors_distances()
    pot = distance_to(sense("source"), dists)
    total = sum_values(pot, float(local_id()) + 1.0)
    avg = mean_values(pot, float(local_id()) + 1.0)
    has_high = collect_or(pot, local_id() >= 10)
    smooth = gossip_mean(float(local_id()))
    any_src = any_node(sense("source"))
    return pot, total, avg, has_high, smooth, any_src


@aggregate
def _branching_and_state_reset():
    # Plain Python `if` statements and conditional expressions: no special branch syntax!
    c, set_c = remember(0)
    c = set_c(c + 1)
    if sense("team_a"):
        peer_sum = neighbors(1).sum()
        store("role", 1)
        if local_id() == 0:
            return peer_sum * 10 + c
        return peer_sum + c
    else:
        inner = counter()
        store("role", 2)
        bonus = 100 if local_id() > 5 else 50
        return neighbors(2).sum() + inner + bonus


@aggregate
def _time_blocks():
    dt = delta_time()
    clk = shared_clock()
    rem = timer(2.5, periodic=True)
    dec = decay(5.0, 1.5)
    prev = delay(float(local_id()), initial=-1.0)
    up = rising_edge(sense("pulse"))
    down = falling_edge(sense("pulse"))
    ema = exponential_filter(float(local_id()), 0.5)
    return dt, clk, rem, dec, prev, up, down, ema


def _random_graph(nodes: int = 24, seed: int = 3):
    rng = random.Random(seed)
    pts = [(round(rng.uniform(0.0, 4.0), 3), round(rng.uniform(0.0, 4.0), 3)) for _ in range(nodes)]
    topo = {
        i: [j for j in range(nodes) if i != j and math.dist(pts[i], pts[j]) <= 1.4]
        for i in range(nodes)
    }
    return pts, topo


def _assert_close(actual, expected):
    assert set(actual.keys()) == set(expected.keys())
    for nid in expected:
        a, e = actual[nid], expected[nid]
        if isinstance(e, tuple):
            assert len(a) == len(e)
            for av, ev in zip(a, e):
                if isinstance(ev, bool):
                    assert bool(av) is ev, (nid, av, ev)
                elif isinstance(ev, float):
                    if math.isinf(ev):
                        assert math.isinf(av) and (av > 0) == (ev > 0), (nid, av, ev)
                    else:
                        assert av == pytest.approx(ev, rel=1e-6, abs=1e-6), (nid, av, ev)
                else:
                    assert av == ev, (nid, av, ev)
        else:
            assert a == pytest.approx(e, rel=1e-6, abs=1e-6), (nid, a, e)


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_synchronous_matches_python_vm_on_core_benchmarks(device: str):
    _, topo = _random_graph(30, seed=4)
    py_rt = SynchronousRuntime(_core_benchmarks)
    gpu_rt = GpuSynchronousRuntime(_core_benchmarks, device=device)
    sensors = {i: {"source": i == 0} for i in topo}

    for _ in range(12):
        _assert_close(gpu_rt.run_round(sensors, topo), py_rt.run_round(sensors, topo))


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_synchronous_matches_metric_gradients_collect_and_gossip(device: str):
    pts, topo = _random_graph(20, seed=9)
    py_rt = SynchronousRuntime(_metric_gradient_and_collect)
    gpu_rt = GpuSynchronousRuntime(_metric_gradient_and_collect, device=device)
    sensors = {i: {"source": i in (0, 11), "position": pts[i]} for i in topo}

    for _ in range(10):
        _assert_close(gpu_rt.run_round(sensors, topo), py_rt.run_round(sensors, topo))


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_synchronous_preserves_if_branch_isolation_state_reset_and_outputs(device: str):
    _, topo = _random_graph(16, seed=5)
    py_rt = SynchronousRuntime(_branching_and_state_reset)
    gpu_rt = GpuSynchronousRuntime(_branching_and_state_reset, device=device)

    for step in range(8):
        # Flip team membership every 2 rounds so branch state resets are exercised!
        sensors = {
            i: {"team_a": ((i + step // 2) % 2 == 0)}
            for i in topo
        }
        _assert_close(gpu_rt.run_round(sensors, topo), py_rt.run_round(sensors, topo))
        assert gpu_rt.outputs == py_rt.outputs


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_synchronous_matches_time_and_reactive_blocks(device: str):
    _, topo = _random_graph(14, seed=12)
    py_rt = SynchronousRuntime(_time_blocks)
    gpu_rt = GpuSynchronousRuntime(_time_blocks, device=device)

    for step in range(8):
        sensors = {
            i: {
                "time": float(step) * (1.0 + 0.05 * (i % 3)),
                "pulse": (step in (1, 2, 5)) and (i % 2 == 0),
            }
            for i in topo
        }
        _assert_close(gpu_rt.run_round(sensors, topo), py_rt.run_round(sensors, topo))

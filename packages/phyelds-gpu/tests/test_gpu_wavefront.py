"""Tests for GpuWavefrontRuntime: concurrent asynchronous batches on CPU and CUDA."""

import pytest
import torch

from phyelds.calculus import aggregate, neighbors
from phyelds.gpu import GpuWavefrontRuntime
from phyelds.gpu.topology import GraphTopology
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time
from phyelds.vm.asynchronous import AsynchronousRuntime
from phyelds.vm.synchronous import SynchronousRuntime
from phyelds.vm.wavefront import Channel, ExponentialClock, PeriodicClock, WeibullClock

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]


@aggregate
def _suite():
    pot = distance_to(sense("source"))
    store("pot", pot)
    return pot, gossip_max(local_id()), count_nodes(pot)


@aggregate
def _max_heard_time():
    return neighbors(local_time()).without_self().max(default=-1.0)


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


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_wavefront_zero_delay_matches_exact_sequential_des(device: str):
    topo_dict = _grid(5, 4)
    topology = GraphTopology.from_neighbors(topo_dict, device=device)
    sensors = {"source": torch.arange(20, device=device) == 0}

    gpu_wf = GpuWavefrontRuntime(
        _suite,
        topology=topology,
        clock=PeriodicClock(1.0, random_phase=True, drift=0.05, jitter=0.05),
        channel=Channel(delay=0.0),
        seed=21,
        device=device,
    )

    events: list[tuple[float, int]] = []
    batch_sizes: list[int] = []
    while gpu_wf.earliest_time() <= 9.0:
        step = gpu_wf.step(sensors)
        batch_sizes.append(len(step.devices))
        for nid in step.devices:
            events.append((gpu_wf.last_time_of(nid), nid))

    assert max(batch_sizes) > 1
    assert sum(batch_sizes) / len(batch_sizes) > 1.5

    # Replay the exact timestamps sequentially on the reference Python AsynchronousRuntime.
    events.sort()
    sequential = AsynchronousRuntime(_suite)
    expected: dict[int, object] = {}
    for when, nid in events:
        expected[nid] = sequential.spike(
            nid, {"source": nid == 0, "time": when}, topo_dict[nid]
        )

    assert gpu_wf.results() == expected
    assert gpu_wf.outputs() == sequential.outputs


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_wavefront_collapses_to_full_system_synchronous_in_worst_case(device: str):
    topo_dict = _grid(5, 4)
    topology = GraphTopology.from_neighbors(topo_dict, device=device)
    sensors = {"source": torch.arange(20, device=device) == 0}

    gpu_wf = GpuWavefrontRuntime(
        _suite,
        topology=topology,
        clock=PeriodicClock(1.0, random_phase=False),
        channel=Channel(delay=0.01),
        device=device,
    )
    py_sync = SynchronousRuntime(_suite)

    for round_idx in range(10):
        step = gpu_wf.step(sensors)
        assert len(step.devices) == 20
        py_sensors = {i: {"source": i == 0, "time": float(round_idx)} for i in topo_dict}
        assert gpu_wf.results() == py_sync.run_round(py_sensors, topo_dict)
        assert gpu_wf.outputs() == py_sync.outputs


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_wavefront_models_in_flight_delay_loss_and_retention(device: str):
    topology = GraphTopology.from_neighbors({0: [1], 1: [0]}, device=device)
    # Explicit initial next_time override to test exact in-flight transitions:
    # t=0.0 (node 0) & t=0.2 (node 1) concurrent under delay=0.5
    gpu_wf = GpuWavefrontRuntime(
        _max_heard_time,
        topology=topology,
        clock=PeriodicClock(1.0, random_phase=False),
        channel=Channel(delay=0.5, retention=1.0),
        device=device,
    )
    gpu_wf.set_next_times(torch.tensor([0.0, 0.2], dtype=torch.float64, device=device))

    # Wavefront 1: both 0 @ 0.0 and 1 @ 0.2 run concurrently -> neither has received anything yet
    s1 = gpu_wf.step({})
    assert set(s1.devices) == {0, 1}
    assert gpu_wf.results() == {0: -1.0, 1: -1.0}

    # Schedule 1 @ 0.7 and 0 @ 1.0: 0's 0.0 arrived at 0.5, 1's 0.2 arrived at 0.7
    gpu_wf.set_next_times(torch.tensor([1.0, 0.7], dtype=torch.float64, device=device))
    gpu_wf.step({})
    assert gpu_wf.results()[1] == pytest.approx(0.0)
    assert gpu_wf.results()[0] == pytest.approx(0.2)

    # Now 0 sent 1.0 (arrives 1.5). Run 1 @ 1.2 while 0 is at 5.0 -> 1 still sees committed 0.0!
    gpu_wf.set_next_times(torch.tensor([5.0, 1.2], dtype=torch.float64, device=device))
    gpu_wf.step({})
    assert gpu_wf.results()[1] == pytest.approx(0.0)

    # Run 1 @ 3.0 -> 0's 1.0 packet arrived at 1.5, age 1.5 > retention 1.0 -> expired (-1.0)!
    gpu_wf.set_next_times(torch.tensor([5.0, 3.0], dtype=torch.float64, device=device))
    gpu_wf.step({})
    assert gpu_wf.results()[1] == pytest.approx(-1.0)

    # Total packet loss (loss=1.0) drops every transmission
    lossy = GpuWavefrontRuntime(
        _max_heard_time,
        topology=topology,
        clock=PeriodicClock(1.0, random_phase=False),
        channel=Channel(delay=0.01, loss=1.0),
        device=device,
    )
    lossy.step({})
    lossy.step({})
    assert lossy.results() == {0: -1.0, 1: -1.0}


@pytest.mark.parametrize("device", DEVICES)
def test_gpu_wavefront_supports_weibull_exponential_and_run_until(device: str):
    pts = torch.tensor([[0.0, 0.0], [0.5, 0.0], [1.0, 0.0]], dtype=torch.float64, device=device)
    sensors = {"source": torch.tensor([True, False, False], device=device)}

    weibull_sim = GpuWavefrontRuntime(
        _suite,
        positions=pts,
        radius=0.75,
        clock=WeibullClock(period=1.0, shape=3.0),
        channel=Channel(delay=0.02, jitter=0.01, loss=0.05),
        window=0.05,
        seed=9,
        device=device,
    )
    res = weibull_sim.run_until(5.0, sensors)
    assert res[0][0] == 0.0

    exp_sim = GpuWavefrontRuntime(
        _suite,
        positions=pts,
        radius=0.75,
        clock=ExponentialClock(rate=2.0),
        seed=4,
        device=device,
    )
    assert exp_sim.run_until(3.0, sensors)
    exp_sim.reset()
    assert exp_sim.results() == {}

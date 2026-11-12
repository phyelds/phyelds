"""Keeps the GPU example of the docs working."""
import importlib.util
import math
from pathlib import Path

import torch

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "gpu.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("gpu_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gpu = _load_example()


def _hops(topology) -> list[float]:
    """The hop distance of each device from device 0, by a breadth-first search."""
    neighbors = topology.to_neighbors()
    hops = [math.inf] * topology.num_devices
    hops[0], frontier = 0, [0]
    while frontier:
        following = []
        for device in frontier:
            for other in neighbors[device]:
                if hops[other] == math.inf:
                    hops[other] = hops[device] + 1
                    following.append(other)
        frontier = following
    return hops


def test_gpu_example_counts_at_the_source_the_devices_its_gradient_reaches():
    torch.manual_seed(0)
    topology, sensors = gpu.world(500)

    distances, counts = gpu.synchronous(topology, sensors, rounds=80)

    assert distances.tolist() == _hops(topology)
    assert counts[0].item() == sum(hops < math.inf for hops in _hops(topology))


def test_gpu_example_spreads_the_gradient_in_wavefronts_too():
    torch.manual_seed(0)
    topology, sensors = gpu.world(500)

    distances, held = gpu.wavefronts(topology, sensors, until=60.0)

    assert bool(held.all())
    assert distances.tolist() == _hops(topology)

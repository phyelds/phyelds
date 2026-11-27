"""
What a graph that changes every round costs the PyTorch backend: building it with
``radius_topology``, against one synchronous round of a program on it.

Each line of the output is one measurement, as JSON. From the root of the repository, with
PyTorch installed:

    PYTHONPATH="packages/phyelds-gpu/src:benchmarks" poetry run python benchmarks/gpu_topology.py
"""
import argparse
import json
import math
import statistics
import time
from collections.abc import Callable
from typing import Any

import torch

from phyelds.gpu import BatchSynchronousRuntime, radius_topology


def timed(work: Callable[[], Any], device: torch.device, repeats: int) -> float:
    """The median time of ``work``, in seconds, after one run to warm up."""
    work()
    times = []
    for _ in range(repeats):
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        start = time.perf_counter()
        work()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def measure(nodes: int, degree: float, device: torch.device, repeats: int, seed: int) -> dict:
    """One measurement: uniform positions with about ``degree`` neighbors within 1."""
    from programs import gradient  # pylint: disable=import-outside-toplevel  # next to this script
    generator = torch.Generator(device=device).manual_seed(seed)
    side = math.sqrt(nodes * math.pi / degree)
    positions = torch.rand(nodes, 2, dtype=torch.float64, device=device, generator=generator)
    positions = positions * side
    topology = radius_topology(positions, 1.0)
    runtime = BatchSynchronousRuntime(gradient, topology)
    sensors = {"source": torch.arange(nodes, device=device) == 0}
    build = timed(lambda: radius_topology(positions, 1.0), device, repeats)
    round_time = timed(lambda: runtime.run_round(sensors), device, repeats)
    return {
        "nodes": nodes,
        "edges": int(topology.senders.numel()),
        "device": torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu",
        "radius_topology_s": build,
        "round_s": round_time,
        "build_over_round": build / round_time,
    }


def main() -> None:
    """Measure each number of nodes and print one JSON line per measurement."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--nodes", nargs="+", type=int, default=[10_000, 100_000, 1_000_000])
    parser.add_argument("--degree", type=float, default=8.0)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    from run import provenance  # pylint: disable=import-outside-toplevel  # next to this script
    device = torch.device(args.device)
    environment = provenance()
    for nodes in args.nodes:
        row = measure(nodes, args.degree, device, args.repeats, args.seed)
        print(json.dumps({**row, "environment": environment}), flush=True)


if __name__ == "__main__":
    main()

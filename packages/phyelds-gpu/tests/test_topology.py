"""Tests for GPU/CPU CSR graph topologies and uniform-grid radius search."""

import math
import random

import pytest
import torch

from phyelds.gpu.topology import GraphTopology, radius_topology

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]


def _brute_force_neighbors(positions: list[tuple[float, ...]], radius: float) -> dict[int, list[int]]:
    return {
        i: [
            j
            for j in range(len(positions))
            if i != j and math.dist(positions[i], positions[j]) <= radius
        ]
        for i in range(len(positions))
    }


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("dims", [2, 3])
@pytest.mark.parametrize("radius", [0.0, 0.8, 2.2])
def test_radius_topology_matches_exact_euclidean_scan(device: str, dims: int, radius: float):
    rng = random.Random(17)
    raw = [tuple(round(rng.uniform(-4.0, 4.0), 2) for _ in range(dims)) for _ in range(90)]
    raw[10] = raw[5]  # duplicate coordinates
    positions = torch.tensor(raw, dtype=torch.float64, device=device)

    topology = radius_topology(positions, radius)
    expected = _brute_force_neighbors(raw, radius)

    assert topology.to_neighbors_dict() == expected
    if topology.sender.numel() > 0:
        assert topology.edge_dist is not None
        first_s = int(topology.sender[0].item())
        first_r = int(topology.receiver[0].item())
        assert topology.edge_dist[0].item() == pytest.approx(math.dist(raw[first_s], raw[first_r]))


@pytest.mark.parametrize("device", DEVICES)
def test_subbatch_extracts_incoming_edges_for_selected_receivers(device: str):
    neighbors = {0: [1, 2], 1: [0], 2: [], 3: [0, 1]}
    topology = GraphTopology.from_neighbors(neighbors, device=device)
    batch = torch.tensor([3, 2, 0], dtype=torch.int64, device=device)

    sub = topology.subbatch(batch)

    assert sub.batch_size == 3
    assert sub.global_sender.tolist() == [0, 1, 1, 2]
    assert sub.local_receiver.tolist() == [0, 0, 2, 2]


def test_topology_handles_empty_or_negative_radius():
    empty = torch.zeros((0, 2), dtype=torch.float64)
    assert radius_topology(empty, 1.0).num_nodes == 0
    pts = torch.tensor([[0.0, 0.0], [0.5, 0.0]], dtype=torch.float64)
    assert radius_topology(pts, -1.0).sender.numel() == 0

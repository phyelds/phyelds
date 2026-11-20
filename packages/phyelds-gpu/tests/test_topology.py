"""
The communication graph as tensors: the radius search on a uniform grid, and the edges into a
batch of devices.
"""
import itertools
import math
import random

import pytest
import torch

from phyelds.gpu import GraphTopology, radius_topology

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]


def _scan(positions: list[tuple[float, ...]], radius: float) -> dict[int, list[int]]:
    """The neighbors within ``radius`` of each device, comparing every pair."""
    return {
        device: [
            other
            for other in range(len(positions))
            if other != device and math.dist(positions[device], positions[other]) <= radius
        ]
        for device in range(len(positions))
    }


def _cloud(count: int, dims: int, seed: int = 17) -> list[tuple[float, ...]]:
    rng = random.Random(seed)
    return [tuple(round(rng.uniform(-4.0, 4.0), 2) for _ in range(dims)) for _ in range(count)]


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("dims", [2, 3])
@pytest.mark.parametrize("radius", [0.0, 0.8, 2.2])
def test_radius_topology_links_the_devices_an_exact_scan_finds(device, dims, radius):
    positions = _cloud(90, dims)
    positions[10] = positions[5]  # two devices in the same place

    topology = radius_topology(torch.tensor(positions, device=device), radius)

    assert topology.to_neighbors() == _scan(positions, radius)


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("dims", [2, 3])
def test_radius_topology_links_the_devices_exactly_at_the_radius(device, dims):
    # A lattice of step 0.5, twice over: many devices share a cell, and many pairs lie
    # exactly at the radius, where rounding would show.
    side = range(-3, 4)
    lattice = [tuple(0.5 * step for step in point) for point in itertools.product(side, repeat=dims)]
    positions = lattice + lattice

    topology = radius_topology(torch.tensor(positions, device=device), 1.0)

    assert topology.to_neighbors() == _scan(positions, 1.0)


@pytest.mark.parametrize("device", DEVICES)
def test_radius_topology_measures_each_edge_the_same_both_ways(device):
    topology = radius_topology(torch.tensor(_cloud(300, 3), device=device), 1.2)

    lengths = dict(zip(zip(topology.senders.tolist(), topology.receivers.tolist()),
                       topology.distances.tolist()))
    assert all(lengths[(receiver, sender)] == length
               for (sender, receiver), length in lengths.items())


@pytest.mark.parametrize("device", DEVICES)
def test_radius_topology_measures_each_edge(device):
    positions = _cloud(60, 2)

    topology = radius_topology(torch.tensor(positions, device=device), 1.5)

    expected = [
        math.dist(positions[sender], positions[receiver])
        for sender, receiver in zip(topology.senders.tolist(), topology.receivers.tolist())
    ]
    assert topology.distances.tolist() == pytest.approx(expected)


def test_radius_topology_links_the_devices_of_a_cloud_spread_over_many_cells():
    rng = random.Random(3)
    positions = []
    for _ in range(20):  # close pairs, a million cells apart along each axis
        centre = tuple(rng.uniform(0.0, 1000.0) for _ in range(3))
        positions += [centre, (centre[0] + 0.0005, *centre[1:])]

    topology = radius_topology(torch.tensor(positions, dtype=torch.float64), 0.001)

    assert topology.to_neighbors() == _scan(positions, 0.001)


def test_radius_topology_rejects_devices_spread_over_too_many_cells_to_key():
    rng = random.Random(5)
    positions = [[rng.uniform(0.0, 1e6) for _ in range(7)] for _ in range(1000)]

    with pytest.raises(ValueError, match="from_neighbors"):
        radius_topology(torch.tensor(positions, dtype=torch.float64), 0.001)


def test_radius_topology_links_nobody_without_devices_or_with_a_negative_radius():
    pair = torch.tensor([[0.0, 0.0], [0.5, 0.0]])

    assert radius_topology(torch.zeros((0, 2)), 1.0).num_devices == 0
    assert radius_topology(pair, -1.0).to_neighbors() == {0: [], 1: []}


@pytest.mark.parametrize("device", DEVICES)
def test_graph_topology_batch_gathers_the_edges_into_each_device_of_the_batch(device):
    topology = GraphTopology.from_neighbors({0: [1, 2], 1: [0], 2: [], 3: [0, 1]}, device=device)

    batch = topology.batch(torch.tensor([3, 2, 0], device=device))

    assert batch.num_devices == 3
    assert batch.senders.tolist() == [0, 1, 1, 2]
    assert batch.receivers.tolist() == [0, 0, 2, 2]
    assert topology.senders[batch.edges].tolist() == batch.senders.tolist()


def test_graph_topology_batch_of_every_device_shares_the_edges_of_the_graph():
    topology = GraphTopology.from_neighbors({0: [1], 1: [0, 2], 2: [1]})

    batch = topology.batch()

    assert batch.devices.tolist() == [0, 1, 2]
    assert batch.senders is topology.senders
    assert batch.receivers is topology.receivers


def test_graph_topology_batch_of_no_devices_has_no_edges():
    topology = GraphTopology.from_neighbors({0: [1], 1: [0]})

    batch = topology.batch(torch.zeros(0, dtype=torch.int64))

    assert batch.num_devices == 0
    assert batch.edges.numel() == 0


@pytest.mark.parametrize("device", DEVICES)
def test_graph_topology_reverse_edges_finds_the_edge_back_of_each_edge(device):
    topology = GraphTopology.from_neighbors({0: [1, 2], 1: [0], 2: []}, device=device)

    reverse = topology.reverse_edges()

    # 1 -> 0 comes back as 0 -> 1, 2 -> 0 has no edge back (2 does not hear 0).
    assert reverse.tolist() == [2, -1, 0]


def test_graph_topology_reverse_edges_of_a_graph_without_edges_is_empty():
    assert GraphTopology.empty(3).reverse_edges().tolist() == []


def test_graph_topology_from_neighbors_ignores_self_loops_and_measures_with_positions():
    positions = torch.tensor([[0.0, 0.0], [3.0, 4.0]])

    topology = GraphTopology.from_neighbors({0: [0, 1], 1: [0]}, positions=positions)

    assert topology.to_neighbors() == {0: [1], 1: [0]}
    assert topology.distances.tolist() == [5.0, 5.0]

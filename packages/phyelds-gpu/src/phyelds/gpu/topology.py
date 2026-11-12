"""
Who hears whom, as tensors: the communication graph of many devices, grouped by receiver, and
the radius search that builds it on a uniform grid, on CPU or GPU.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import itertools

import torch

# Cells a little wider than the radius, so that rounding never hides a neighbor in a farther
# cell, as in the uniform grid of the simulator.
_MARGIN = 1.0 + 1e-6


@dataclass(frozen=True)
class BatchEdges:
    """The edges into a batch of devices: where what they hear comes from."""

    devices: torch.Tensor
    """The ids of the devices of the batch (``int64 [M]``)."""
    edges: torch.Tensor
    """The index of each edge into the batch among the edges of the topology (``int64 [E]``)."""
    senders: torch.Tensor
    """The id of the device each edge comes from (``int64 [E]``)."""
    receivers: torch.Tensor
    """The position in ``devices`` of the device each edge goes to (``int64 [E]``)."""

    @property
    def num_devices(self) -> int:
        """How many devices the batch holds."""
        return int(self.devices.numel())


@dataclass(frozen=True)
class GraphTopology:
    """
    A directed communication graph on a torch device: an edge goes from a sender to a
    receiver that hears it. The edges are grouped by receiver, and sorted by sender in each
    group, so that the edges into device ``i`` are ``offsets[i]:offsets[i + 1]``.
    """

    num_devices: int
    """How many devices the graph links, with ids ``0`` to ``num_devices - 1``."""
    senders: torch.Tensor
    """The device each edge comes from (``int64 [E]``)."""
    receivers: torch.Tensor
    """The device each edge goes to (``int64 [E]``), in non-decreasing order."""
    offsets: torch.Tensor
    """Where the edges into each device start, and then end (``int64 [num_devices + 1]``)."""
    distances: torch.Tensor | None = None
    """The length of each edge (``float64 [E]``), if the positions of the devices are known."""

    @property
    def device(self) -> torch.device:
        """The torch device holding the tensors of the graph."""
        return self.offsets.device

    @classmethod
    def empty(cls, num_devices: int, device: torch.device | str = "cpu") -> "GraphTopology":
        """
        A graph of devices that hear nobody.

        Args:
            num_devices: How many devices the graph has.
            device: The torch device holding its tensors.

        Returns:
            A ``GraphTopology`` without edges.
        """
        none = torch.zeros(0, dtype=torch.int64, device=device)
        offsets = torch.zeros(num_devices + 1, dtype=torch.int64, device=device)
        return cls(num_devices, none, none, offsets)

    @classmethod
    def from_neighbors(
        cls,
        neighbors: Mapping[int, Iterable[int]],
        *,
        num_devices: int | None = None,
        positions: torch.Tensor | None = None,
        device: torch.device | str = "cpu",
    ) -> "GraphTopology":
        """
        The graph in which each device hears its neighbors.

        Args:
            neighbors: The ids of the neighbors of each device, by its id; a device hears
                its neighbors, never itself.
            num_devices: How many devices the graph has; ``len(neighbors)`` by default.
            positions: The position of each device (``[num_devices, D]``), to measure the
                edges; none by default.
            device: The torch device holding the tensors of the graph.

        Returns:
            The ``GraphTopology`` of ``neighbors``.
        """
        count = len(neighbors) if num_devices is None else num_devices
        senders: list[int] = []
        receivers: list[int] = []
        for receiver in range(count):
            peers = sorted(peer for peer in neighbors.get(receiver, ()) if peer != receiver)
            senders.extend(peers)
            receivers.extend([receiver] * len(peers))
        sender_ids = torch.tensor(senders, dtype=torch.int64, device=device)
        receiver_ids = torch.tensor(receivers, dtype=torch.int64, device=device)
        distances = None
        if positions is not None:
            located = positions.to(device=device, dtype=torch.float64)
            distances = _lengths(located[sender_ids] - located[receiver_ids])
        return cls(count, sender_ids, receiver_ids, _offsets(receiver_ids, count), distances)

    def batch(self, devices: torch.Tensor | None = None) -> BatchEdges:
        """
        The edges into a batch of devices.

        Args:
            devices: The ids of the devices of the batch (``int64 [M]``); every device by
                default, sharing the tensors of the graph.

        Returns:
            The ``BatchEdges`` of the batch, grouped by receiver in the order of ``devices``.
        """
        if devices is None:
            every = torch.arange(self.num_devices, dtype=torch.int64, device=self.device)
            all_edges = torch.arange(self.senders.numel(), dtype=torch.int64, device=self.device)
            return BatchEdges(every, all_edges, self.senders, self.receivers)
        devices = devices.to(device=self.device, dtype=torch.int64)
        starts = self.offsets[devices]
        lengths = self.offsets[devices + 1] - starts
        receivers = torch.repeat_interleave(
            torch.arange(devices.numel(), dtype=torch.int64, device=self.device), lengths
        )
        # The position of each edge in the group of its receiver.
        firsts = torch.cumsum(lengths, dim=0) - lengths
        rank = torch.arange(receivers.numel(), dtype=torch.int64, device=self.device)
        edges = starts[receivers] + rank - firsts[receivers]
        return BatchEdges(devices, edges, self.senders[edges], receivers)

    def to_neighbors(self) -> dict[int, list[int]]:
        """
        The neighbors of each device, as plain Python values.

        Returns:
            The ids of the devices each device hears, in increasing order, by its id.
        """
        offsets = self.offsets.tolist()
        senders = self.senders.tolist()
        return {
            device: senders[offsets[device]:offsets[device + 1]]
            for device in range(self.num_devices)
        }


def radius_topology(positions: torch.Tensor, radius: float) -> GraphTopology:
    """
    The graph in which each device hears the others within ``radius`` of it.

    The search goes through a uniform grid of cells as wide as ``radius``, on the torch
    device of ``positions``: each device is compared only with those in its cell and in the
    cells around it. The neighbors are those of ``radius_neighborhood`` in the simulator.

    Args:
        positions: The position of each device (``[N, D]``).
        radius: How far a device hears; with a negative one, nobody hears anybody.

    Returns:
        The ``GraphTopology`` of the devices, with the length of each edge.
    """
    count = int(positions.shape[0])
    located = positions.to(dtype=torch.float64)
    if count == 0 or radius < 0.0:
        return GraphTopology.empty(count, positions.device)

    grid = _Grid.build(located, radius * _MARGIN if radius > 0.0 else 1.0)
    parts = [
        found
        for shift in itertools.product((-1, 0, 1), repeat=grid.dims)
        if (found := grid.pairs_within(located, radius, shift)) is not None
    ]
    if not parts:
        return GraphTopology.empty(count, positions.device)
    senders = torch.cat([part[0] for part in parts])
    receivers = torch.cat([part[1] for part in parts])
    distances = torch.cat([part[2] for part in parts])
    order = torch.argsort(receivers * count + senders)
    receivers = receivers[order]
    return GraphTopology(
        count, senders[order], receivers, _offsets(receivers, count), distances[order]
    )


def _lengths(vectors: torch.Tensor) -> torch.Tensor:
    """The Euclidean length of each row of ``vectors``."""
    # pylint cannot see into the C extension of torch, where vector_norm is a function.
    return torch.linalg.vector_norm(vectors, dim=-1)  # pylint: disable=not-callable


def _offsets(receivers: torch.Tensor, count: int) -> torch.Tensor:
    """Where the edges into each of ``count`` devices start in sorted ``receivers``, then end."""
    return torch.searchsorted(
        receivers, torch.arange(count + 1, dtype=torch.int64, device=receivers.device)
    )


@dataclass(frozen=True)
class _Grid:
    """Devices sorted by cell, with the cells that hold at least one of them."""

    sorted_devices: torch.Tensor
    """The devices, ordered by the key of their cell."""
    keys: torch.Tensor
    """The keys of the cells holding devices, in increasing order."""
    starts: torch.Tensor
    """Where the devices of each cell start in ``sorted_devices``."""
    counts: torch.Tensor
    """How many devices each cell holds."""
    strides: torch.Tensor
    """How much the key of a cell grows with each coordinate of the cell."""
    dims: int
    """How many coordinates a position has."""

    @classmethod
    def build(cls, positions: torch.Tensor, side: float) -> "_Grid":
        """The grid of cells as wide as ``side`` holding ``positions``."""
        count, dims = int(positions.shape[0]), int(positions.shape[1])
        cells = torch.floor(positions / side).to(torch.int64)
        cells = cells - cells.min(dim=0).values
        # One empty cell on each side, so that shifted cells never wrap into another row.
        extents = cells.max(dim=0).values + 3
        strides = torch.ones(dims, dtype=torch.int64, device=positions.device)
        for axis in range(dims - 2, -1, -1):
            strides[axis] = strides[axis + 1] * extents[axis + 1]
        keys = ((cells + 1) * strides).sum(dim=-1)
        order = torch.argsort(
            keys * (count + 1) + torch.arange(count, dtype=torch.int64, device=positions.device)
        )
        unique_keys, counts = torch.unique_consecutive(keys[order], return_counts=True)
        starts = torch.cumsum(counts, dim=0) - counts
        return cls(order, unique_keys, starts, counts, strides, dims)

    def pairs_within(
        self, positions: torch.Tensor, radius: float, shift: tuple[int, ...]
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None:
        """
        The pairs of devices within ``radius`` of each other, the receiver in a cell and the
        sender in the cell ``shift`` away: their senders, receivers and distances.
        """
        targets = self.keys + (torch.tensor(shift, device=self.keys.device) * self.strides).sum()
        found = torch.searchsorted(self.keys, targets)
        safe = torch.clamp(found, max=self.keys.numel() - 1)
        matched = (found < self.keys.numel()) & (self.keys[safe] == targets)
        if not bool(matched.any()):
            return None
        receiver_cells = torch.nonzero(matched).squeeze(-1)
        senders, receivers = self._cross(receiver_cells, safe[receiver_cells])
        apart = senders != receivers
        senders, receivers = senders[apart], receivers[apart]
        distances = _lengths(positions[senders] - positions[receivers])
        within = distances <= radius
        if not bool(within.any()):
            return None
        return senders[within], receivers[within], distances[within]

    def _cross(
        self, receiver_cells: torch.Tensor, sender_cells: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Every pair of a device in a receiver cell and one in the matching sender cell."""
        sender_counts = self.counts[sender_cells]
        sizes = self.counts[receiver_cells] * sender_counts
        pair = torch.repeat_interleave(
            torch.arange(sizes.numel(), dtype=torch.int64, device=sizes.device), sizes
        )
        rank = torch.arange(int(sizes.sum()), dtype=torch.int64, device=sizes.device)
        rank = rank - (torch.cumsum(sizes, dim=0) - sizes)[pair]
        row = torch.div(rank, sender_counts[pair], rounding_mode="floor")
        column = rank - row * sender_counts[pair]
        receivers = self.sorted_devices[self.starts[receiver_cells][pair] + row]
        senders = self.sorted_devices[self.starts[sender_cells][pair] + column]
        return senders, receivers

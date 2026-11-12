"""CSR graph topology and vectorized uniform-grid radius search on PyTorch CPU/CUDA."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import itertools
import torch

_MARGIN = 1.0 + 1e-6


@dataclass(frozen=True)
class SubbatchEdges:
    """Incoming edges restricted to an active subset ``batch_ids`` of ``M`` receivers."""

    batch_ids: torch.Tensor
    """Global node IDs of the ``M`` active devices (`int64 [M]`)."""
    edge_indices: torch.Tensor
    """Indices into the parent ``GraphTopology`` edge arrays (`int64 [E_B]`)."""
    global_sender: torch.Tensor
    """Global sender node ID for each incoming edge (`int64 [E_B]`)."""
    local_receiver: torch.Tensor
    """Index in ``0..M-1`` of the receiving batch device (`int64 [E_B]`)."""

    @property
    def batch_size(self) -> int:
        """Number of devices in the active batch."""
        return int(self.batch_ids.numel())


def _empty_topology(count: int, dev: torch.device) -> "GraphTopology":
    empty = torch.zeros(0, dtype=torch.int64, device=dev)
    indptr = torch.zeros(count + 1, dtype=torch.int64, device=dev)
    return GraphTopology(count, empty, empty, indptr, None)


@dataclass(frozen=True)
class GraphTopology:
    """Directed communication graph stored in receiver-grouped CSR format on a Torch device."""

    num_nodes: int
    sender: torch.Tensor
    receiver: torch.Tensor
    indptr: torch.Tensor
    edge_dist: torch.Tensor | None = None

    @property
    def device(self) -> torch.device:
        """Torch device hosting the topology arrays."""
        return self.indptr.device

    @staticmethod
    def from_neighbors(
        neighbors: Mapping[int, Iterable[int]],
        *,
        num_nodes: int | None = None,
        positions: torch.Tensor | None = None,
        device: torch.device | str = "cpu",
    ) -> "GraphTopology":
        """Build a CSR ``GraphTopology`` from a Python adjacency mapping ``0..N-1``."""
        dev = torch.device(device)
        count = len(neighbors) if num_nodes is None else num_nodes
        if count == 0:
            return _empty_topology(0, dev)

        send_list: list[int] = []
        recv_list: list[int] = []
        lengths: list[int] = []
        for recv in range(count):
            peers = sorted(other for other in neighbors.get(recv, ()) if other != recv)
            lengths.append(len(peers))
            send_list.extend(peers)
            recv_list.extend([recv] * len(peers))

        sender = torch.tensor(send_list, dtype=torch.int64, device=dev)
        receiver = torch.tensor(recv_list, dtype=torch.int64, device=dev)
        indptr = torch.zeros(count + 1, dtype=torch.int64, device=dev)
        indptr[1:] = torch.cumsum(torch.tensor(lengths, dtype=torch.int64, device=dev), dim=0)
        dists = (
            torch.linalg.vector_norm(
                positions.to(device=dev, dtype=torch.float64)[sender]
                - positions.to(device=dev, dtype=torch.float64)[receiver],
                dim=-1,
            )
            if positions is not None and sender.numel() > 0
            else None
        )
        return GraphTopology(count, sender, receiver, indptr, dists)

    def subbatch(self, batch_ids: torch.Tensor) -> SubbatchEdges:
        """Slice incoming edges for the ``M`` receiver IDs in ``batch_ids``."""
        dev = self.device
        batch_ids = batch_ids.to(device=dev, dtype=torch.int64)
        count = int(batch_ids.numel())
        if count == 0 or self.sender.numel() == 0:
            empty = torch.zeros(0, dtype=torch.int64, device=dev)
            return SubbatchEdges(batch_ids, empty, empty, empty)

        starts = self.indptr[batch_ids]
        lengths = self.indptr[batch_ids + 1] - starts
        total_edges = int(lengths.sum().item())
        if total_edges == 0:
            empty = torch.zeros(0, dtype=torch.int64, device=dev)
            return SubbatchEdges(batch_ids, empty, empty, empty)

        local_receiver = torch.repeat_interleave(
            torch.arange(count, dtype=torch.int64, device=dev), lengths
        )
        prefix = torch.zeros(count, dtype=torch.int64, device=dev)
        if count > 1:
            prefix[1:] = torch.cumsum(lengths[:-1], dim=0)
        offsets = torch.arange(total_edges, dtype=torch.int64, device=dev) - prefix[local_receiver]
        edge_indices = starts[local_receiver] + offsets
        return SubbatchEdges(
            batch_ids=batch_ids,
            edge_indices=edge_indices,
            global_sender=self.sender[edge_indices],
            local_receiver=local_receiver,
        )

    def full_batch(self) -> SubbatchEdges:
        """Return ``SubbatchEdges`` spanning all ``0..N-1`` nodes without copying edge arrays."""
        all_ids = torch.arange(self.num_nodes, dtype=torch.int64, device=self.device)
        all_edges = torch.arange(self.sender.numel(), dtype=torch.int64, device=self.device)
        return SubbatchEdges(all_ids, all_edges, self.sender, self.receiver)

    def to_neighbors_dict(self) -> dict[int, list[int]]:
        """Convert the CSR graph back to a Python adjacency dictionary."""
        ptr = self.indptr.cpu().tolist()
        snd = self.sender.cpu().tolist()
        return {node: snd[ptr[node]:ptr[node + 1]] for node in range(self.num_nodes)}


@dataclass(frozen=True)
class _CellIndex:
    sorted_nodes: torch.Tensor
    unique_keys: torch.Tensor
    cell_starts: torch.Tensor
    cell_counts: torch.Tensor
    strides: torch.Tensor
    dims: int


def _build_cell_index(pos: torch.Tensor, side: float) -> _CellIndex:
    dev = pos.device
    count, dims = int(pos.shape[0]), int(pos.shape[1])
    raw_cells = torch.floor(pos / side).to(torch.int64)
    shifted = raw_cells - raw_cells.min(dim=0).values
    extents = shifted.max(dim=0).values + 3
    strides = torch.ones(dims, dtype=torch.int64, device=dev)
    for axis in range(dims - 2, -1, -1):
        strides[axis] = strides[axis + 1] * extents[axis + 1]

    keys = ((shifted + 1) * strides).sum(dim=-1)
    order = torch.argsort(
        keys * (count + 1) + torch.arange(count, dtype=torch.int64, device=dev)
    )
    unique_keys, cell_counts = torch.unique_consecutive(keys[order], return_counts=True)
    cell_starts = torch.zeros(unique_keys.numel(), dtype=torch.int64, device=dev)
    if unique_keys.numel() > 1:
        cell_starts[1:] = torch.cumsum(cell_counts[:-1], dim=0)
    return _CellIndex(order, unique_keys, cell_starts, cell_counts, strides, dims)


def _expand_cell_pairs(
    index: _CellIndex, src_cells: torch.Tensor, dst_cells: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    dev = index.sorted_nodes.device
    counts_b = index.cell_counts[dst_cells]
    pair_sizes = index.cell_counts[src_cells] * counts_b
    total = int(pair_sizes.sum().item())
    pair_idx = torch.repeat_interleave(
        torch.arange(pair_sizes.numel(), dtype=torch.int64, device=dev), pair_sizes
    )
    pair_offsets = torch.zeros(pair_sizes.numel(), dtype=torch.int64, device=dev)
    if pair_sizes.numel() > 1:
        pair_offsets[1:] = torch.cumsum(pair_sizes[:-1], dim=0)
    local_k = torch.arange(total, dtype=torch.int64, device=dev) - pair_offsets[pair_idx]
    cb = counts_b[pair_idx]
    offset_a = torch.div(local_k, cb, rounding_mode="floor")
    receivers = index.sorted_nodes[index.cell_starts[src_cells][pair_idx] + offset_a]
    senders = index.sorted_nodes[index.cell_starts[dst_cells][pair_idx] + local_k - offset_a * cb]
    return senders, receivers


def _collect_shift_edges(
    pos: torch.Tensor, radius: float, index: _CellIndex, delta: tuple[int, ...]
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor] | None:
    delta_t = torch.tensor(delta, dtype=torch.int64, device=pos.device)
    target_keys = index.unique_keys + (delta_t * index.strides).sum()
    idx = torch.searchsorted(index.unique_keys, target_keys)
    num_cells = index.unique_keys.numel()
    safe_idx = torch.clamp(idx, max=max(0, num_cells - 1))
    matched = (idx < num_cells) & (index.unique_keys[safe_idx] == target_keys)
    if not bool(matched.any().item()):
        return None
    src_cells = torch.nonzero(matched, as_tuple=False).squeeze(-1)
    snd, rcv = _expand_cell_pairs(index, src_cells, safe_idx[src_cells])
    snd, rcv = snd[snd != rcv], rcv[snd != rcv]
    if snd.numel() == 0:
        return None
    dists = torch.linalg.vector_norm(pos[snd] - pos[rcv], dim=-1)
    within = dists <= radius
    return (snd[within], rcv[within], dists[within]) if bool(within.any().item()) else None


def radius_topology(positions: torch.Tensor, radius: float) -> GraphTopology:
    """
    Build a ``GraphTopology`` linking nodes within Euclidean ``radius`` using GPU cell hashing.

    Args:
        positions: Coordinate tensor of shape ``[N, D]`` on CPU or CUDA.
        radius: Maximum Euclidean communication distance.

    Returns:
        CSR ``GraphTopology`` ordered by ``(receiver, sender)`` with ``edge_dist`` populated.
    """
    dev = positions.device
    pos = positions.to(dtype=torch.float64)
    count = int(pos.shape[0])
    if count == 0 or radius < 0.0:
        return _empty_topology(count, dev)

    index = _build_cell_index(pos, radius * _MARGIN if radius > 0.0 else 1.0)
    parts = [
        found
        for delta in itertools.product((-1, 0, 1), repeat=index.dims)
        if (found := _collect_shift_edges(pos, radius, index, delta)) is not None
    ]
    if not parts:
        return _empty_topology(count, dev)

    all_snd = torch.cat([part[0] for part in parts])
    all_rcv = torch.cat([part[1] for part in parts])
    edge_order = torch.argsort(all_rcv * count + all_snd)
    sorted_rcv = all_rcv[edge_order]
    indptr = torch.searchsorted(
        sorted_rcv, torch.arange(count + 1, dtype=torch.int64, device=dev)
    )
    return GraphTopology(
        count,
        all_snd[edge_order],
        sorted_rcv,
        indptr,
        torch.cat([part[2] for part in parts])[edge_order],
    )

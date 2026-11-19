"""
What the devices of a batch keep from a round to the next, as tensors with a row per device or
per edge: their state, and the messages of synchronous rounds.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import torch

from phyelds.gpu.fields import BatchField, as_field, default_rows
from phyelds.gpu.tensors import where_rows
from phyelds.gpu.topology import BatchEdges, GraphTopology

# A value of each device of a batch, and which devices hold one.
Rows = tuple[torch.Tensor, torch.Tensor]


@dataclass
class _FieldSlot:  # pylint: disable=too-many-instance-attributes
    """
    A state kept as a field on some devices: of each device its value, whether it holds it,
    and its default; of each edge into it, its value and whether it holds it. A value the
    same for every neighbor is a field with no entries, whose default is that value.
    """

    local: torch.Tensor
    local_present: torch.Tensor
    default: torch.Tensor
    held: torch.Tensor
    values: torch.Tensor
    present: torch.Tensor

    @classmethod
    def of_rows(cls, slot: Rows, num_edges: int) -> "_FieldSlot":
        """The values of ``slot``, each the same for every neighbor, as fields."""
        values, held = slot
        return cls(values, torch.ones_like(held), values.clone(), held,
                   *_empty_rows(num_edges, values))

    def read(self, edges: BatchEdges) -> tuple[BatchField, torch.Tensor]:
        """The field of the devices of ``edges``, and which of them hold one."""
        devices, index = edges.devices, edges.edges
        stored = BatchField(
            edges, self.local[devices], self.values[index], self.present[index],
            local_present=self.local_present[devices], default=self.default[devices],
        )
        return stored, self.held[devices]

    def write(self, edges: BatchEdges, value: BatchField, mask: torch.Tensor) -> None:
        """Store ``value`` for the devices of ``edges`` in ``mask``, and for the edges into them."""
        devices, on_edges = edges.devices[mask], mask[edges.receivers]
        index = edges.edges[on_edges]
        self.local = _assigned(self.local, devices, value.local_values[mask])
        self.local_present[devices] = value.local_present[mask]
        self.default = _assigned(self.default, devices, default_rows(value)[mask])
        self.held[devices] = True
        self.values = _assigned(self.values, index, value.values[on_edges])
        self.present[index] = value.present[on_edges]

    def move(self, index: torch.Tensor, kept: torch.Tensor) -> None:
        """Keep on each new edge the value of the old edge at ``index``, where ``kept`` holds."""
        self.values, self.present = move_rows((self.values, self.present), index, kept)


class States:
    """
    The state of every device: for each alignment key, a value of each device and whether
    it holds one; a field, where some device keeps one.

    Args:
        topology: The devices and the edges between them.
    """

    def __init__(self, topology: GraphTopology):
        self.count = topology.num_devices
        self.num_edges = int(topology.senders.numel())
        self.device = topology.device
        self._slots: dict[int, Rows | _FieldSlot] = {}

    def read(self, key: int, edges: BatchEdges) -> tuple[Any, torch.Tensor] | None:
        """
        The values of the devices of ``edges`` at ``key``, rows or a field, and which of them
        hold one; none if no one does.
        """
        slot = self._slots.get(key)
        if slot is None:
            return None
        if isinstance(slot, _FieldSlot):
            return slot.read(edges)
        values, held = slot
        return values[edges.devices], held[edges.devices]

    def write(self, key: int, edges: BatchEdges, value: Any, mask: torch.Tensor) -> None:
        """Store ``value``, rows or a field, at ``key`` for the devices of ``edges`` in ``mask``."""
        slot = self._slots.get(key)
        if isinstance(value, BatchField) and not isinstance(slot, _FieldSlot):
            rows = _empty_rows(self.count, value.local_values) if slot is None else slot
            slot = _FieldSlot.of_rows(rows, self.num_edges)
        if isinstance(slot, _FieldSlot):
            slot.write(edges, as_field(edges, value), mask)
            self._slots[key] = slot
        else:
            self._slots[key] = write_rows(slot, self.count, edges.devices, value, mask)

    def forget(self, key: int, devices: torch.Tensor, mask: torch.Tensor) -> None:
        """Drop the values at ``key`` of the ``devices`` of ``mask``."""
        slot = self._slots.get(key)
        if slot is not None:
            _held(slot)[devices[mask]] = False

    def keep_read(self, devices: torch.Tensor, reads: Mapping[int, torch.Tensor]) -> None:
        """Drop the values of ``devices`` they did not read, as a device drops its unused state."""
        for key, slot in self._slots.items():
            read = reads.get(key)
            _held(slot)[devices if read is None else devices[~read]] = False

    def forget_devices(self, devices: torch.Tensor) -> None:
        """
        Forget the state of ``devices``, as if they joined now; the others keep theirs.

        Args:
            devices: The ids of the devices to forget (``int64 [M]``).
        """
        for slot in self._slots.values():
            _held(slot)[devices] = False

    def move_to(self, topology: GraphTopology, index: torch.Tensor, kept: torch.Tensor) -> None:
        """
        Follow the devices onto ``topology``: a field kept as state keeps its value on the
        edges ``topology`` shares with the previous graph, and holds none on the new ones.

        Args:
            topology: The new graph of the same devices.
            index: The previous edge of each edge of ``topology`` (see
                ``GraphTopology.edges_from``).
            kept: Whether the previous graph has it.
        """
        self.num_edges = int(topology.senders.numel())
        for slot in self._slots.values():
            if isinstance(slot, _FieldSlot):
                slot.move(index, kept)

    def clear(self) -> None:
        """Forget the state of every device."""
        self._slots.clear()


class Inbox(Protocol):  # pylint: disable=too-few-public-methods
    """Where a batch of devices reads what its neighbors sent."""

    def read(self, key: int, edges: BatchEdges) -> Rows | None:
        """What each edge into ``edges`` carries at ``key``, and which of them carry it."""


@dataclass
class Outbox:
    """What the devices of a batch sent in a round, by alignment key."""

    shared: dict[int, Rows] = field(default_factory=dict)
    """A value of each device for all its neighbors, and whether it sent one: for a field, its
    default."""
    addressed: dict[int, Rows] = field(default_factory=dict)
    """For a field, its value on each edge into the batch, which the receiver addresses back to
    the sender, and whether it holds one: the sender then reads it instead of the default."""


class SynchronousMessages:
    """
    The messages of synchronous rounds: in a round every device reads what its neighbors
    sent in the previous one.

    Args:
        topology: The devices and the edges between them.
    """

    def __init__(self, topology: GraphTopology):
        self.count = topology.num_devices
        self.num_edges = int(topology.senders.numel())
        self.device = topology.device
        self._back = topology.reverse_edges()
        self._sent: dict[int, Rows] = {}
        self._addressed: dict[int, Rows] = {}
        """The value addressed along each edge of the topology, and whether there is one."""

    def read(self, key: int, edges: BatchEdges) -> Rows | None:
        """What the sender of each edge sent at ``key`` in the previous round, if it did."""
        slot = self._sent.get(key)
        if slot is None:
            return None
        values, sent = slot[0][edges.senders], slot[1][edges.senders]
        addressed = self._addressed.get(key)
        if addressed is not None:
            values = where_rows(addressed[1][edges.edges], addressed[0][edges.edges], values)
        return values, sent

    def publish(self, edges: BatchEdges, outbox: Outbox) -> None:
        """Replace the messages of the devices of ``edges`` with ``outbox``, for the next round."""
        devices = edges.devices
        for key, (_, sent) in self._sent.items():
            if key not in outbox.shared:
                sent[devices] = False
        for key, (values, mask) in outbox.shared.items():
            slot = self._sent.get(key)
            if slot is not None:
                slot[1][devices] = False
            self._sent[key] = write_rows(slot, self.count, devices, values, mask)
        index, has_back = edges_back(self._back, edges)
        for key in set(self._addressed) | set(outbox.addressed):
            addressed = outbox.addressed.get(key)
            if addressed is None:
                self._addressed[key][1][index] = False
                continue
            values, present = addressed
            self._addressed[key] = put_rows(
                self._addressed.get(key), self.num_edges, index,
                values[has_back], present[has_back],
            )

    def forget_devices(self, devices: torch.Tensor) -> None:
        """
        Forget what ``devices`` sent; what the others sent them stays.

        A value addressed along an edge is read only with what its sender sent to all its
        neighbors, so forgetting the latter is enough, until the next ``publish``.

        Args:
            devices: The ids of the devices whose messages to forget (``int64 [M]``).
        """
        for _, sent in self._sent.values():
            sent[devices] = False

    def move_to(self, topology: GraphTopology, index: torch.Tensor, kept: torch.Tensor) -> None:
        """
        Follow the devices onto ``topology``: what each device sent to all its neighbors
        stays; a value addressed along an edge stays if ``topology`` keeps the edge.

        Args:
            topology: The new graph of the same devices.
            index: The previous edge of each edge of ``topology`` (see
                ``GraphTopology.edges_from``).
            kept: Whether the previous graph has it.
        """
        self.num_edges = int(topology.senders.numel())
        self._back = topology.reverse_edges()
        for key, slot in self._addressed.items():
            self._addressed[key] = move_rows(slot, index, kept)

    def clear(self) -> None:
        """Forget every message."""
        self._sent.clear()
        self._addressed.clear()


def edges_back(back: torch.Tensor, edges: BatchEdges) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Where the values a batch addresses on the edges into it travel: on the edge back of each,
    from the receiver to the sender.

    Args:
        back: The edge back of each edge of the topology, or ``-1`` (see
            ``GraphTopology.reverse_edges``).
        edges: The edges into the batch.

    Returns:
        The edges back, among those of the topology, and which edges into the batch have one.
    """
    targets = back[edges.edges]
    has_back = targets >= 0
    return targets[has_back], has_back


def _held(slot: Rows | _FieldSlot) -> torch.Tensor:
    """Which devices hold a value in ``slot``."""
    return slot.held if isinstance(slot, _FieldSlot) else slot[1]


def _assigned(stored: torch.Tensor, index: torch.Tensor, values: torch.Tensor) -> torch.Tensor:
    """``stored`` with ``values`` at ``index``, in a type that holds both."""
    if stored.dtype != values.dtype:
        stored = stored.to(torch.promote_types(stored.dtype, values.dtype))
    stored[index] = values.to(stored.dtype)
    return stored


def put_rows(
    slot: Rows | None, count: int, index: torch.Tensor, values: torch.Tensor,
    carried: torch.Tensor,
) -> Rows:
    """``slot`` of ``count`` rows with ``values`` and ``carried`` at ``index``."""
    stored, held = _empty_rows(count, values) if slot is None else slot
    stored = _assigned(stored, index, values)
    held[index] = carried
    return stored, held


def move_rows(slot: Rows, index: torch.Tensor, kept: torch.Tensor) -> Rows:
    """The rows of ``slot`` at ``index``, held only where ``kept`` holds."""
    values, held = slot
    if values.shape[0] == 0:
        return _empty_rows(int(index.numel()), values)
    return values[index], held[index] & kept


def write_rows(
    slot: Rows | None, count: int, devices: torch.Tensor, values: torch.Tensor, mask: torch.Tensor
) -> Rows:
    """``slot`` of ``count`` devices, with ``values`` written for the ``devices`` of ``mask``."""
    stored, held = _empty_rows(count, values) if slot is None else slot
    stored = _assigned(stored, devices[mask], values[mask])
    held[devices[mask]] = True
    return stored, held


def _empty_rows(count: int, values: torch.Tensor) -> Rows:
    """``count`` rows shaped as those of ``values``, none of them held."""
    stored = torch.zeros((count, *values.shape[1:]), dtype=values.dtype, device=values.device)
    return stored, torch.zeros(count, dtype=torch.bool, device=values.device)

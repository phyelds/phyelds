"""
The engine of a batch of devices: the operations of ``phyelds.vm.Engine`` on tensors, with one
row per device, for the devices running the current code.

The calculus stays the one of the core: ``remember``, ``neighbors`` and ``exchange`` call the
operations of this engine, and ``@aggregate`` rewrites ``if`` statements and expressions into
its ``branch`` and ``choose``, which run each side for the devices taking it.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import torch

from phyelds import engine
from phyelds.gpu.fields import BatchField
from phyelds.gpu.tensors import as_rows, where_rows
from phyelds.gpu.topology import BatchEdges, GraphTopology
from phyelds.vm import Engine, NodeContext
from phyelds.vm.internal import CompactPaths

_IDLE = object()  # what a side of a branch that no device takes returns
_LOCAL = object()  # the default of a neighbor field when none is given: the local value

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
        return cls(
            values, torch.ones_like(held), values.clone(), held,
            torch.zeros((num_edges, *values.shape[1:]), dtype=values.dtype, device=values.device),
            torch.zeros(num_edges, dtype=torch.bool, device=values.device),
        )

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
        self.default = _assigned(self.default, devices, _default_rows(value)[mask])
        self.held[devices] = True
        self.values = _assigned(self.values, index, value.values[on_edges])
        self.present[index] = value.present[on_edges]


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
            if slot is None:
                nobody = torch.zeros_like(mask)
                slot = _written(None, self.count, edges.devices, value.local_values, nobody)
            slot = _FieldSlot.of_rows(slot, self.num_edges)
        if isinstance(slot, _FieldSlot):
            slot.write(edges, _as_field(edges, value), mask)
            self._slots[key] = slot
        else:
            self._slots[key] = _written(slot, self.count, edges.devices, value, mask)

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
            self._sent[key] = _written(slot, self.count, devices, values, mask)
        # What a device addresses on an edge into it travels on the edge back.
        back = self._back[edges.edges]
        has_back = back >= 0
        for key in set(self._addressed) | set(outbox.addressed):
            addressed = outbox.addressed.get(key)
            if addressed is None:
                self._addressed[key][1][back[has_back]] = False
                continue
            values, present = addressed
            self._addressed[key] = _put(
                self._addressed.get(key), self.num_edges, back[has_back],
                values[has_back], present[has_back],
            )

    def clear(self) -> None:
        """Forget every message."""
        self._sent.clear()
        self._addressed.clear()


class BatchContext(NodeContext):
    """
    The context of a batch of devices: their ids, their sensors and what they store.

    Args:
        devices: The ids of the devices of the batch (``int64 [M]``).
        sensors: The sensors of every device, by name: a tensor with a row per device of the
            whole system, or one value for all.
        batch_engine: The engine running the batch: the devices that store are those running
            the current code.
    """

    def __init__(
        self, devices: torch.Tensor, sensors: Mapping[str, Any], batch_engine: "BatchEngine"
    ):
        super().__init__(devices, dict(sensors))
        self._engine = batch_engine
        self.stored: dict[str, Rows] = {}
        """What the devices stored, by name: a value of each device and whether it stored one."""

    def sense(self, sensor_name: str) -> Any:
        value = self.sensors.get(sensor_name)
        if isinstance(value, torch.Tensor) and value.ndim > 0:
            return value[self.node_id]
        return value

    def store(self, output_name: str, value: Any) -> None:
        running = self._engine.running
        values = as_rows(value, running.numel(), running.device)
        previous = self.stored.get(output_name)
        if previous is None:
            self.stored[output_name] = (values, running.clone())
        else:
            self.stored[output_name] = (
                where_rows(running, values, previous[0]), previous[1] | running
            )


@dataclass
class _Round:
    """What the devices of a batch leave behind in a round: the values they read and sent."""

    reads: dict[int, torch.Tensor] = field(default_factory=dict)
    outbox: Outbox = field(default_factory=Outbox)


class BatchEngine(Engine):  # pylint: disable=too-many-instance-attributes
    """
    An engine that runs a batch of devices at once, each value holding a row per device.

    Args:
        edges: The devices of the batch and the edges into them.
        states: The state of every device, kept from a round to the next.
        inbox: What the neighbors sent.
        sensors: The sensors of every device, by name (see ``BatchContext``).
    """

    vectorized = True

    def __init__(
        self, edges: BatchEdges, states: States, inbox: Inbox, sensors: Mapping[str, Any]
    ):
        super().__init__()
        self.edges = edges
        self.states = states
        self.inbox = inbox
        self.running = torch.ones(edges.num_devices, dtype=torch.bool, device=edges.devices.device)
        """Which devices of the batch run the current code."""
        self.node_context: BatchContext = BatchContext(edges.devices, sensors, self)
        self._paths = CompactPaths()
        self._stack: list[int] = []
        self._counts = [0]
        self._round = _Round()

    def setup(self, node_context, messages, state=None):
        raise NotImplementedError("a batch engine is built for each round of its devices")

    def enter(self, name: str) -> None:
        counter = self._counts[-1]
        self._counts[-1] = counter + 1
        parent = self._stack[-1] if self._stack else None
        self._stack.append(self._paths.segment(parent, name, counter))
        self._counts.append(0)

    def exit(self) -> None:
        if self._stack:
            self._stack.pop()
            self._counts.pop()

    def current_path(self) -> list:
        return self._stack.copy()

    def read_state(self, stack: list | None = None) -> Any:
        key = self._key(stack)
        self._mark_read(key)
        slot = self.states.read(key, self.edges)
        nothing = self._rows(None)
        return nothing if slot is None else merge(slot[1], slot[0], nothing)

    def read_state_or(self, init: Any, stack: list | None = None) -> Any:
        key = self._key(stack)
        self._mark_read(key)
        value = self._value(init)
        slot = self.states.read(key, self.edges)
        if slot is not None:
            value = merge(slot[1], slot[0], value)
        self.states.write(key, self.edges, value, self.running)
        return value

    def write_state(self, value: Any, stack: list | None = None) -> None:
        self.states.write(self._key(stack), self.edges, self._value(value), self.running)

    def forget(self, _self_path: list) -> None:
        self.states.forget(self._key(_self_path), self.edges.devices, self.running)

    def own_value(self, value: Any) -> Any:
        if not isinstance(value, BatchField):
            return value
        return where_rows(value.local_present, value.local_values, _default_rows(value))

    def default_value(self, value: Any) -> Any:
        return value.default if isinstance(value, BatchField) else value

    def send(self, data: Any, stack: list | None = None) -> None:
        key = self._key(stack)
        outbox = self._round.outbox
        if isinstance(data, BatchField):
            shared, addressed = _default_rows(data), (data.values, data.present)
        else:
            shared, addressed = self._rows(data), None
        previous = outbox.shared.get(key)
        if previous is None:
            outbox.shared[key] = (shared, self.running.clone())
        else:
            outbox.shared[key] = (
                where_rows(self.running, shared, previous[0]), previous[1] | self.running
            )
        if addressed is not None or key in outbox.addressed:
            outbox.addressed[key] = self._addressed(outbox.addressed.get(key), addressed)

    def neighbor_field(
        self, local: Any, path: list | None = None, default: Any = _LOCAL, *,
        addressed: bool = False,
    ) -> BatchField:
        # The messages already hold, on each edge, the value its sender addressed to it.
        del addressed
        local_rows = self._rows(local)
        received = self.inbox.read(self._key(path), self.edges)
        if received is None:
            values = local_rows[self.edges.receivers]
            present = torch.zeros_like(self.edges.receivers, dtype=torch.bool)
        else:
            values, present = received
        return BatchField(
            self.edges, local_rows, values, present,
            default=local_rows if default is _LOCAL else default,
        )

    def branch(self, condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]):
        mask = self._mask(condition)
        if mask is None:
            return super().branch(condition, if_true, if_false)
        return self._split(mask, if_true, if_false, aligned=True)

    def choose(self, condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]):
        mask = self._mask(condition)
        if mask is None:
            return super().choose(condition, if_true, if_false)
        return self._split(mask, if_true, if_false, aligned=False)

    def run(self, program: Callable[[], Any]) -> Any:
        """
        Run ``program`` once for the devices of the batch, with this engine as the current one.

        Returns:
            What the program returned, with a row per device of the batch.
        """
        token = engine.set(self)
        try:
            return program()
        finally:
            engine.reset(token)

    def finish(self) -> Outbox:
        """
        End the round of the batch: drop the state its devices did not read.

        Returns:
            What the devices sent, by alignment key.
        """
        self.states.keep_read(self.edges.devices, self._round.reads)
        return self._round.outbox

    def _key(self, stack: list | None) -> int:
        return self._paths.key(self._stack if stack is None else stack)

    def _rows(self, value: Any) -> torch.Tensor:
        return as_rows(value, self.edges.num_devices, self.edges.devices.device)

    def _value(self, value: Any) -> Any:
        """``value`` as the engine keeps it: a field as it is, anything else as rows."""
        return value if isinstance(value, BatchField) else self._rows(value)

    def _addressed(self, previous: Rows | None, addressed: Rows | None) -> Rows:
        """
        The values addressed on the edges into the running devices replaced with
        ``addressed``, or dropped if it is none; those into the other devices kept.
        """
        on_edges = self.running[self.edges.receivers]
        if addressed is None:
            return previous[0], previous[1] & ~on_edges
        values, present = addressed
        if previous is None:
            return values, present & on_edges
        return (
            where_rows(on_edges, values, previous[0]), torch.where(on_edges, present, previous[1])
        )

    def _mark_read(self, key: int) -> None:
        read = self._round.reads.get(key)
        self._round.reads[key] = self.running.clone() if read is None else read | self.running

    def _mask(self, condition: Any) -> torch.Tensor | None:
        """The devices for which ``condition`` holds; none if it has a single truth value."""
        if isinstance(condition, BatchField):
            raise TypeError("a field has no truth value: reduce it first")
        if not isinstance(condition, torch.Tensor) or condition.ndim == 0:
            return None
        return self._rows(condition).to(torch.bool)

    def _split(self, mask: torch.Tensor, if_true, if_false, *, aligned: bool) -> Any:
        """
        Run each side for the running devices taking it, and merge what they return. Both
        sides of a branch enter their alignment point with the same counter, as a device
        enters only one of them: the paths are those of the devices on their own.
        """
        running, counter = self.running, self._counts[-1]
        left, right = running & mask, running & ~mask
        outcomes = []
        for side_mask, side, name in ((left, if_true, "left"), (right, if_false, "right")):
            if not bool(side_mask.any()):
                outcomes.append(_IDLE)
                continue
            self.running = side_mask
            if aligned:
                self._counts[-1] = counter
                self.enter(name)
            try:
                outcomes.append(side())
            finally:
                if aligned:
                    self.exit()
                self.running = running
        if outcomes[0] is _IDLE or outcomes[1] is _IDLE:
            return outcomes[1] if outcomes[0] is _IDLE else outcomes[0]
        return merge(left, outcomes[0], outcomes[1])


class Diverged:
    """
    A value that differs from device to device and has no rows: a function, or a field on
    some devices only, that the branches of an ``if`` left in a variable. Using it fails.
    """

    def __getattr__(self, name: str) -> Any:
        raise TypeError(_DIVERGED)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(_DIVERGED)

    def __bool__(self) -> bool:
        raise TypeError(_DIVERGED)


_DIVERGED = (
    "the branches of an if left different functions or fields in this variable on different "
    "devices: a batch engine cannot use it after the if"
)


def merge(mask: torch.Tensor, chosen: Any, other: Any) -> Any:
    """
    The values of ``chosen`` for the devices of ``mask``, those of ``other`` for the rest.

    Tuples merge item by item, fields entry by entry, and numbers and tensors row by row,
    with ``None`` as NaN; a field and a number merge as fields, the number a field with no
    entries whose default is the number. Any other values become a ``Diverged``, which fails
    when used.
    """
    if chosen is other:
        return chosen
    if isinstance(chosen, tuple) and isinstance(other, tuple) and len(chosen) == len(other):
        return tuple(merge(mask, *pair) for pair in zip(chosen, other))
    if not all(isinstance(value, BatchField) or _has_rows(value) for value in (chosen, other)):
        return Diverged()
    if isinstance(chosen, BatchField) or isinstance(other, BatchField):
        edges = (chosen if isinstance(chosen, BatchField) else other).edges
        return BatchField.merged(mask, _as_field(edges, chosen), _as_field(edges, other))
    rows, device = mask.numel(), mask.device
    return where_rows(mask, as_rows(chosen, rows, device), as_rows(other, rows, device))


def _has_rows(value: Any) -> bool:
    """Whether ``value`` can be a row of each device: a number, ``None`` or a tensor."""
    return value is None or isinstance(value, (bool, int, float, torch.Tensor))


def _as_field(edges: BatchEdges, value: Any) -> BatchField:
    """``value`` as a field: a value of each device is a field with no entries, its default."""
    if isinstance(value, BatchField):
        return value
    rows = as_rows(value, edges.num_devices, edges.devices.device)
    absent = torch.zeros_like(edges.receivers, dtype=torch.bool)
    return BatchField(edges, rows, rows[edges.receivers], absent, default=rows)


def _default_rows(value: BatchField) -> torch.Tensor:
    """The default of ``value`` for each device, NaN if it has none."""
    return as_rows(value.default, value.edges.num_devices, value.edges.devices.device)


def _held(slot: Rows | _FieldSlot) -> torch.Tensor:
    """Which devices hold a value in ``slot``."""
    return slot.held if isinstance(slot, _FieldSlot) else slot[1]


def _assigned(stored: torch.Tensor, index: torch.Tensor, values: torch.Tensor) -> torch.Tensor:
    """``stored`` with ``values`` at ``index``, in a type that holds both."""
    if stored.dtype != values.dtype:
        stored = stored.to(torch.promote_types(stored.dtype, values.dtype))
    stored[index] = values.to(stored.dtype)
    return stored


def _put(slot: Rows | None, count: int, index: torch.Tensor, values: torch.Tensor,
         carried: torch.Tensor) -> Rows:
    """``slot`` of ``count`` rows with ``values`` and ``carried`` at ``index``."""
    if slot is None:
        slot = (torch.zeros((count, *values.shape[1:]), dtype=values.dtype, device=values.device),
                torch.zeros(count, dtype=torch.bool, device=values.device))
    stored, held = slot
    stored = _assigned(stored, index, values)
    held[index] = carried
    return stored, held


def _written(
    slot: Rows | None, count: int, devices: torch.Tensor, values: torch.Tensor, mask: torch.Tensor
) -> Rows:
    """``slot`` of ``count`` devices, with ``values`` written for the ``devices`` of ``mask``."""
    if slot is None:
        stored = torch.zeros((count, *values.shape[1:]), dtype=values.dtype, device=values.device)
        held = torch.zeros(count, dtype=torch.bool, device=values.device)
    else:
        stored, held = slot
        if stored.dtype != values.dtype:
            common_type = torch.promote_types(stored.dtype, values.dtype)
            stored, values = stored.to(common_type), values.to(common_type)
    stored[devices[mask]] = values[mask].to(stored.dtype)
    held[devices[mask]] = True
    return stored, held

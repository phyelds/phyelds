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
from phyelds.gpu.topology import BatchEdges
from phyelds.vm import Engine, NodeContext
from phyelds.vm.internal import CompactPaths

_IDLE = object()  # what a side of a branch that no device takes returns
_LOCAL = object()  # the default of a neighbor field when none is given: the local value

# A value of each device of a batch, and which devices hold one.
Rows = tuple[torch.Tensor, torch.Tensor]


class States:
    """
    The state of every device: for each alignment key, a value of each device and whether
    it holds one.

    Args:
        count: How many devices there are.
        device: The torch device of the tensors.
    """

    def __init__(self, count: int, device: torch.device | str):
        self.count = count
        self.device = torch.device(device)
        self._slots: dict[int, Rows] = {}

    def read(self, key: int, devices: torch.Tensor) -> Rows | None:
        """The values of ``devices`` at ``key`` and which of them hold one; none if no one does."""
        slot = self._slots.get(key)
        if slot is None:
            return None
        values, held = slot
        return values[devices], held[devices]

    def write(self, key: int, devices: torch.Tensor, values: torch.Tensor, mask: torch.Tensor):
        """Store ``values`` at ``key`` for the ``devices`` of ``mask``."""
        self._slots[key] = _written(self._slots.get(key), self.count, devices, values, mask)

    def forget(self, key: int, devices: torch.Tensor, mask: torch.Tensor) -> None:
        """Drop the values at ``key`` of the ``devices`` of ``mask``."""
        slot = self._slots.get(key)
        if slot is not None:
            slot[1][devices[mask]] = False

    def keep_read(self, devices: torch.Tensor, reads: Mapping[int, torch.Tensor]) -> None:
        """Drop the values of ``devices`` they did not read, as a device drops its unused state."""
        for key, (_, held) in self._slots.items():
            read = reads.get(key)
            held[devices if read is None else devices[~read]] = False

    def clear(self) -> None:
        """Forget the state of every device."""
        self._slots.clear()


class Inbox(Protocol):  # pylint: disable=too-few-public-methods
    """Where a batch of devices reads what its neighbors sent."""

    def read(self, key: int, edges: BatchEdges) -> Rows | None:
        """What each edge into ``edges`` carries at ``key``, and which of them carry it."""


class SynchronousMessages:
    """
    The messages of synchronous rounds: in a round every device reads what its neighbors
    sent in the previous one.

    Args:
        count: How many devices there are.
        device: The torch device of the tensors.
    """

    def __init__(self, count: int, device: torch.device | str):
        self.count = count
        self.device = torch.device(device)
        self._sent: dict[int, Rows] = {}

    def read(self, key: int, edges: BatchEdges) -> Rows | None:
        """What the sender of each edge sent at ``key`` in the previous round, if it did."""
        slot = self._sent.get(key)
        if slot is None:
            return None
        values, sent = slot
        return values[edges.senders], sent[edges.senders]

    def publish(self, devices: torch.Tensor, outbox: Mapping[int, Rows]) -> None:
        """Replace the messages of ``devices`` with ``outbox``, for the next round."""
        for key, (_, sent) in self._sent.items():
            if key not in outbox:
                sent[devices] = False
        for key, (values, mask) in outbox.items():
            slot = self._sent.get(key)
            if slot is not None:
                slot[1][devices] = False
            self._sent[key] = _written(slot, self.count, devices, values, mask)

    def clear(self) -> None:
        """Forget every message."""
        self._sent.clear()


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
    outbox: dict[int, Rows] = field(default_factory=dict)


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

    def read_state(self, stack: list | None = None) -> torch.Tensor:
        key = self._key(stack)
        self._mark_read(key)
        slot = self.states.read(key, self.edges.devices)
        nothing = self._rows(None)
        return nothing if slot is None else where_rows(slot[1], slot[0], nothing)

    def read_state_or(self, init: Any, stack: list | None = None) -> torch.Tensor:
        key = self._key(stack)
        self._mark_read(key)
        value = self._rows(init)
        slot = self.states.read(key, self.edges.devices)
        if slot is not None:
            value = where_rows(slot[1], slot[0], value)
        self.states.write(key, self.edges.devices, value, self.running)
        return value

    def write_state(self, value: Any, stack: list | None = None) -> None:
        self.states.write(self._key(stack), self.edges.devices, self._rows(value), self.running)

    def forget(self, _self_path: list) -> None:
        self.states.forget(self._key(_self_path), self.edges.devices, self.running)

    def send(self, data: Any, stack: list | None = None) -> None:
        if isinstance(data, BatchField):
            raise TypeError("a batch engine sends a value of each device, not a field")
        key = self._key(stack)
        values = self._rows(data)
        previous = self._round.outbox.get(key)
        if previous is None:
            self._round.outbox[key] = (values, self.running.clone())
        else:
            self._round.outbox[key] = (
                where_rows(self.running, values, previous[0]), previous[1] | self.running
            )

    def neighbor_field(
        self, local: Any, path: list | None = None, default: Any = _LOCAL, *,
        addressed: bool = False,
    ) -> BatchField:
        del addressed  # a batch engine sends no fields: no value is addressed to a device
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

    def finish(self) -> dict[int, Rows]:
        """
        End the round of the batch: drop the state its devices did not read.

        Returns:
            What the devices sent, by alignment key: a value of each and whether it sent one.
        """
        self.states.keep_read(self.edges.devices, self._round.reads)
        return self._round.outbox

    def _key(self, stack: list | None) -> int:
        return self._paths.key(self._stack if stack is None else stack)

    def _rows(self, value: Any) -> torch.Tensor:
        return as_rows(value, self.edges.num_devices, self.edges.devices.device)

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
    with ``None`` as NaN; any other values become a ``Diverged``, which fails when used.
    """
    if chosen is other:
        return chosen
    if isinstance(chosen, tuple) and isinstance(other, tuple) and len(chosen) == len(other):
        return tuple(merge(mask, *pair) for pair in zip(chosen, other))
    if isinstance(chosen, BatchField) and isinstance(other, BatchField):
        return BatchField.merged(mask, chosen, other)
    if not (_has_rows(chosen) and _has_rows(other)):
        return Diverged()
    rows, device = mask.numel(), mask.device
    return where_rows(mask, as_rows(chosen, rows, device), as_rows(other, rows, device))


def _has_rows(value: Any) -> bool:
    """Whether ``value`` can be a row of each device: a number, ``None`` or a tensor."""
    return value is None or isinstance(value, (bool, int, float, torch.Tensor))


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

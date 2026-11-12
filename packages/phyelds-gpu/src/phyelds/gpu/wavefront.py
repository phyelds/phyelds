"""
Wavefronts of a batch of devices on a torch device: devices with their own clocks, talking
over a channel with delays and losses, running together when they do not depend on each other,
as ``phyelds.experimental.wavefront`` does, with one row per device.

The clocks and the channel are those of ``phyelds.experimental.wavefront``: they compute with
arithmetic only, so the same objects compute on tensors here.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import math
from typing import Any

import torch

from phyelds.experimental.wavefront import Channel, Clock, Draws, PeriodicClock
from phyelds.gpu.engine import BatchEngine, Rows, States, _written
from phyelds.gpu.tensors import as_rows
from phyelds.gpu.topology import BatchEdges, GraphTopology


def select_batch(
    next_times: torch.Tensor,
    topology: GraphTopology,
    *,
    lookahead: float,
    delay: float,
    until: float | None = None,
) -> torch.Tensor:
    """
    Pick the devices that run their next round together, as ``select_wavefront`` does.

    Args:
        next_times: The time of the next round of each device (``float64 [N]``).
        topology: Who hears whom: a device waits for the neighbors it hears.
        lookahead: How far past the earliest pending round a wavefront reaches.
        delay: How long a message takes, at the least, to reach a neighbor.
        until: The time after which no round runs; none by default.

    Returns:
        The ids of the devices of the wavefront, in increasing order (``int64 [M]``).
    """
    none = torch.zeros(0, dtype=torch.int64, device=next_times.device)
    if next_times.numel() == 0:
        return none
    earliest = float(next_times.min())
    if until is not None and earliest > until:
        return none
    cap = earliest + lookahead if until is None else min(earliest + lookahead, until)
    senders, receivers = topology.senders, topology.receivers
    arrival = next_times[senders] + delay
    due = next_times[receivers]
    # A sender blocks a receiver if a message of its next round can arrive by the receiver's
    # round; with no delay, of two devices due together the one with the lower id runs first.
    blocking = (arrival < due) | ((arrival == due) & ((delay > 0.0) | (senders < receivers)))
    blocked = torch.zeros_like(next_times, dtype=torch.bool)
    blocked[receivers[blocking]] = True
    return torch.nonzero((next_times <= cap) & ~blocked).squeeze(-1)


class Mailbox:
    """
    What each edge carries over a channel: the last message that arrived and the next one in
    flight, with their arrival times, as the links of ``WavefrontRuntime`` keep them. A
    message is the whole outbox of a round of the sender, by alignment key.

    Args:
        topology: The edges.
        channel: How late messages arrive, which are lost, and for how long they are heard.
    """

    def __init__(self, topology: GraphTopology, channel: Channel):
        count = int(topology.senders.numel())
        self.topology = topology
        self.channel = channel
        self._arrived_at = torch.full((count,), -math.inf, dtype=torch.float64,
                                      device=topology.device)
        self._pending_at = torch.full((count,), math.inf, dtype=torch.float64,
                                      device=topology.device)
        self._arrived: dict[int, Rows] = {}
        self._pending: dict[int, Rows] = {}

    def read(self, key: int, edges: BatchEdges, times: torch.Tensor) -> Rows | None:
        """
        What each edge into ``edges`` carries at ``key`` when its receiver runs at ``times``.

        Returns:
            The values and which edges carry one heard at that time; none if no edge ever did.
        """
        if key not in self._arrived and key not in self._pending:
            return None
        index, now = edges.edges, times[edges.receivers]
        arrived = self._pending_at[index] <= now
        values, carried = _pick(arrived, self._slot(self._pending, key, index),
                                self._slot(self._arrived, key, index))
        arrival = torch.where(arrived, self._pending_at[index], self._arrived_at[index])
        return values, carried & self.channel.heard(now - arrival)

    def transmit(
        self, devices: torch.Tensor, times: torch.Tensor, outbox: Mapping[int, Rows],
        uniform: Callable[[int], torch.Tensor],
    ) -> None:
        """
        Send the outbox of ``devices``, which ran at ``times``, on every edge out of them.

        Args:
            devices: The ids of the senders (``int64 [M]``).
            times: When each of them ran (``float64 [M]``).
            outbox: What they sent, by alignment key: a value of each and whether it sent it.
            uniform: Uniform draws in ``[0, 1)``, ``uniform(n)`` of them, for the channel.
        """
        senders = self.topology.senders
        row = torch.full((self.topology.num_devices,), -1, dtype=torch.int64,
                         device=senders.device)
        row[devices] = torch.arange(devices.numel(), device=senders.device)
        sending = torch.nonzero(row[senders] >= 0).squeeze(-1)
        sending = sending[~self.channel.lost(uniform(sending.numel()))]
        rows = row[senders[sending]]
        arrival = self.channel.arrival(times[rows], uniform(sending.numel()))
        # The message in flight has arrived by the time the next one does: it is the last
        # arrived now; one that would arrive later is overtaken, and lost.
        arrived = sending[self._pending_at[sending] <= arrival]
        for key in set(self._arrived) | set(self._pending):
            pending = self._slot(self._pending, key, arrived)
            self._arrived[key] = _put(self._arrived.get(key), self._edges, arrived, *pending)
        self._arrived_at[arrived] = self._pending_at[arrived]
        self._pending_at[sending] = arrival
        for key in set(self._pending) | set(outbox):
            values, sent = outbox.get(key, (None, None))
            if values is None:
                self._pending[key][1][sending] = False
                continue
            self._pending[key] = _put(self._pending.get(key), self._edges, sending,
                                      values[rows], sent[rows])

    def clear(self) -> None:
        """Forget every message."""
        self._arrived_at.fill_(-math.inf)
        self._pending_at.fill_(math.inf)
        self._arrived.clear()
        self._pending.clear()

    @property
    def _edges(self) -> int:
        return int(self.topology.senders.numel())

    @staticmethod
    def _slot(slots: Mapping[int, Rows], key: int, index: torch.Tensor) -> Rows | None:
        slot = slots.get(key)
        return None if slot is None else (slot[0][index], slot[1][index])


@dataclass(frozen=True)
class _Reading:
    """The mailbox as the devices of a wavefront read it, each at the time of its round."""

    mailbox: Mailbox
    times: torch.Tensor

    def read(self, key: int, edges: BatchEdges) -> Rows | None:
        """What each edge into ``edges`` carries at ``key``, when its receiver runs."""
        return self.mailbox.read(key, edges, self.times)


@dataclass
class _Run:
    """What a run of a wavefront runtime keeps, from its start or its last reset."""

    device_draws: torch.Tensor
    next_times: torch.Tensor
    last_times: torch.Tensor
    results: Any = None
    outputs: dict[str, Rows] = field(default_factory=dict)
    now: float = 0.0


@dataclass(frozen=True)
class BatchWavefrontStep:
    """What a wavefront ran."""

    time: float
    """The latest round of the wavefront."""
    devices: torch.Tensor
    """The ids of its devices (``int64 [M]``)."""
    results: Any
    """What the program returned for them, with a row per device of the wavefront."""


class BatchWavefrontRuntime:  # pylint: disable=too-many-instance-attributes
    """
    Runs an aggregate program in wavefronts of devices that do not depend on each other, on
    the torch device of the graph, as ``WavefrontRuntime`` of ``phyelds.experimental`` does.

    Every device of the graph takes part from the start, with the clock and the channel of
    ``phyelds.experimental.wavefront``; their randomness comes from a torch generator.

    Args:
        program: The ``@aggregate`` function to run.
        topology: Who hears whom.
        clock: When each device runs; ``PeriodicClock(1.0)`` by default.
        channel: How messages travel; an ideal ``Channel()`` by default.
        window: How close two rounds may be and still run together, besides the delay of
            the channel; ``None`` for the delay alone.
        seed: The seed of the randomness of the clocks and of the channel.

    Raises:
        ValueError: If ``window`` is negative.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        program: Callable[[], Any],
        topology: GraphTopology,
        *,
        clock: Clock | None = None,
        channel: Channel | None = None,
        window: float | None = None,
        seed: int = 0,
    ):
        if window is not None and window < 0:
            raise ValueError(f"window must be non-negative, not {window}")
        self.program = program
        self.topology = topology
        self.clock: Clock = PeriodicClock(1.0) if clock is None else clock
        self.channel = Channel() if channel is None else channel
        self.window = window
        self.seed = seed
        self._states = States(topology.num_devices, topology.device)
        self._mailbox = Mailbox(topology, self.channel)
        self._generator = torch.Generator(device=topology.device)
        self._run = self._start()

    def reset(self) -> None:
        """Forget the state, the messages, the outputs and the clocks of every device."""
        self._states.clear()
        self._mailbox.clear()
        self._run = self._start()

    @property
    def time(self) -> float:
        """The earliest round of the last wavefront, or the ``until`` of the last run."""
        return self._run.now

    @property
    def last_times(self) -> torch.Tensor:
        """When each device last ran; NaN if it has not yet."""
        return self._run.last_times

    @property
    def results(self) -> Any:
        """The latest result of each device: rows ``(values, held)`` for each value."""
        return self._run.results

    @property
    def outputs(self) -> dict[str, Rows]:
        """What each device stored in its latest round, by name: ``(values, stored)``."""
        return self._run.outputs

    def next_time(self) -> float:
        """The time of the next round of any device."""
        next_times = self._run.next_times
        return float(next_times.min()) if next_times.numel() else math.inf

    def step(self, sensors: Mapping[str, Any], *, until: float | None = None) -> BatchWavefrontStep:
        """
        Run the next wavefront.

        Args:
            sensors: The sensors of the devices, by name: a tensor with a row per device, or
                one value for all; ``"time"`` is the time of each round, unless given.
            until: The time after which no round runs; none by default.

        Returns:
            What the wavefront ran; no devices if no round is due by ``until``.
        """
        delay = max(self.channel.delay, 0.0 if self.window is None else self.window)
        run = self._run
        devices = select_batch(
            run.next_times, self.topology, lookahead=self.clock.period, delay=delay, until=until
        )
        if devices.numel() == 0:
            return BatchWavefrontStep(run.now, devices, None)
        times = run.next_times[devices]
        run.now = max(run.now, float(times.min()))
        batch = BatchEngine(
            self.topology.batch(devices), self._states, _Reading(self._mailbox, times),
            {"time": run.next_times, **sensors},
        )
        result = batch.run(self.program)
        self._mailbox.transmit(devices, times, batch.finish(), self._uniform)
        self._keep(devices, result, batch.node_context.stored)
        run.last_times[devices] = times
        run.next_times[devices] = times + self.clock.interval(self._draws(devices))
        return BatchWavefrontStep(float(times.max()), devices, result)

    def run_until(self, until: float, sensors: Mapping[str, Any]) -> Any:
        """
        Run wavefronts until no round is due by ``until``.

        Returns:
            The latest result of each device, as ``results``.
        """
        while self.next_time() <= until:
            if self.step(sensors, until=until).devices.numel() == 0:
                break
        self._run.now = max(self._run.now, until)
        return self.results

    def _start(self) -> _Run:
        """A run from time zero: the seed drawn again, each device waiting for its first round."""
        count, device = self.topology.num_devices, self.topology.device
        self._generator.manual_seed(self.seed)
        device_draws = self._uniform(count)
        first = self.clock.first(Draws(device_draws, *self._fresh(count)))
        return _Run(
            device_draws=device_draws,
            next_times=as_rows(first, count, device).to(torch.float64),
            last_times=torch.full((count,), math.nan, dtype=torch.float64, device=device),
        )

    def _uniform(self, count: int) -> torch.Tensor:
        return torch.rand(count, generator=self._generator, dtype=torch.float64,
                          device=self.topology.device)

    def _fresh(self, count: int) -> tuple[torch.Tensor, torch.Tensor]:
        """New uniform and exponential draws, ``count`` of each."""
        return self._uniform(count), -torch.log1p(-self._uniform(count))

    def _draws(self, devices: torch.Tensor) -> Draws:
        uniform, exponential = self._fresh(devices.numel())
        return Draws(self._run.device_draws[devices], uniform, exponential)

    def _keep(self, devices: torch.Tensor, result: Any, stored: Mapping[str, Rows]) -> None:
        """Keep the results and the outputs of the devices of a wavefront."""
        run, count = self._run, self.topology.num_devices
        run.results = _kept(run.results, result, count, devices)
        for _, held in run.outputs.values():
            held[devices] = False
        for name, (values, mask) in stored.items():
            run.outputs[name] = _written(run.outputs.get(name), count, devices, values, mask)


def _kept(previous: Any, result: Any, count: int, devices: torch.Tensor) -> Any:
    """The rows of every device, ``previous``, with the ``result`` of ``devices`` written."""
    if isinstance(result, tuple):
        olds = previous if isinstance(previous, tuple) else (None,) * len(result)
        return tuple(_kept(old, item, count, devices) for old, item in zip(olds, result))
    rows = devices.numel()
    every = torch.ones(rows, dtype=torch.bool, device=devices.device)
    old = previous if isinstance(previous, tuple) and len(previous) == 2 else None
    return _written(old, count, devices, as_rows(result, rows, devices.device), every)


def _pick(chosen: torch.Tensor, first: Rows | None, second: Rows | None) -> Rows:
    """The rows of ``first`` where ``chosen`` holds, of ``second`` elsewhere; none is empty."""
    sample = first if first is not None else second
    empty = (torch.zeros_like(sample[0]), torch.zeros_like(sample[1]))
    first, second = first or empty, second or empty
    mask = chosen.view(-1, *[1] * (sample[0].ndim - 1))
    values = torch.where(mask, *_common(first[0], second[0]))
    return values, torch.where(chosen, first[1], second[1])


def _common(first: torch.Tensor, second: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    dtype = torch.promote_types(first.dtype, second.dtype)
    return first.to(dtype), second.to(dtype)


def _put(slot: Rows | None, count: int, index: torch.Tensor, values: torch.Tensor,
         carried: torch.Tensor) -> Rows:
    """``slot`` of ``count`` edges with ``values`` and ``carried`` at ``index``."""
    if slot is None:
        slot = (torch.zeros((count, *values.shape[1:]), dtype=values.dtype, device=values.device),
                torch.zeros(count, dtype=torch.bool, device=values.device))
    stored, held = slot
    if stored.dtype != values.dtype:
        dtype = torch.promote_types(stored.dtype, values.dtype)
        stored, values = stored.to(dtype), values.to(dtype)
    stored[index] = values.to(stored.dtype)
    held[index] = carried
    return stored, held

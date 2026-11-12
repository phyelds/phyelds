"""
The wavefront runtime: runs an aggregate program in batches of devices that do not depend on
each other, from event-by-event asynchronous rounds to synchronous rounds of every device.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
import math
import random
from typing import Any

from phyelds.experimental.wavefront.channel import Channel, _LinkSlot
from phyelds.experimental.wavefront.clocks import Clock, Draws, PeriodicClock
from phyelds.experimental.wavefront.schedule import WorldNeighbors, select_wavefront
from phyelds.vm.synchronous import RoundRunner

WorldSensors = Mapping[Hashable, Mapping[str, Any]]


@dataclass(frozen=True)
class WavefrontStep:
    """Outcome of executing one concurrent batch (wavefront) of devices."""

    time: float
    """Latest wakeup timestamp among the devices executed in this wavefront."""
    devices: tuple[Hashable, ...]
    """Devices that executed concurrently in this wavefront."""
    results: dict[Hashable, Any]
    """Program return values for the devices of this wavefront."""
    outputs: dict[Hashable, dict[str, Any]]
    """Outputs written with ``store`` by the devices of this wavefront."""


class WavefrontRuntime:  # pylint: disable=too-many-instance-attributes
    """
    Execute an aggregate program in concurrent batches of causally independent devices.

    At each step, every device whose wakeup falls within the lookahead horizon and has no
    neighbor capable of delivering a message before its wakeup runs in the same concurrent
    batch. When ``channel.delay == 0`` and ``window == 0``, batches are exact conservative
    DES wavefronts matching single-event execution; when all clocks are aligned and
    ``channel.delay > 0`` (or ``window > 0``), each batch spans the whole network like
    ``SynchronousRuntime``.

    Args:
        program: The ``@aggregate`` function to run on each device.
        clock: Per-device wakeup clock; ``PeriodicClock(1.0)`` by default.
        channel: Communication channel model; ideal zero-delay ``Channel()`` by default.
        window: Minimum concurrency window ``>= 0`` relaxing causal dependencies closer than
            ``window`` time units; ``None`` uses ``channel.delay`` alone.
        seed: Random seed for device clocks and channel losses/jitter.
        workers: Number of worker threads executing each concurrent wavefront batch.

    Raises:
        ValueError: If ``window < 0`` or ``workers < 1``.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        program: Callable[[], Any],
        *,
        clock: Clock | None = None,
        channel: Channel | None = None,
        window: float | None = None,
        seed: int = 0,
        workers: int = 1,
    ):
        if window is not None and window < 0:
            raise ValueError(f"window must be non-negative, not {window}")
        self._runner = RoundRunner(program, workers=workers)
        self.program = program
        self.clock: Clock = PeriodicClock(1.0) if clock is None else clock
        self.channel: Channel = Channel() if channel is None else channel
        self.window = window
        self.seed = seed
        self.workers = workers
        self.results: dict[Hashable, Any] = {}
        self.outputs: dict[Hashable, dict[str, Any]] = {}
        self._states: dict[Hashable, dict[str, Any]] = {}
        self._links: dict[Hashable, dict[Hashable, _LinkSlot]] = {}
        self._next_time: dict[Hashable, float] = {}
        self._last_time: dict[Hashable, float] = {}
        self._device_rngs: dict[Hashable, tuple[random.Random, float]] = {}
        self._channel_rng = random.Random(f"{seed}:channel")
        self._now = 0.0

    @property
    def time(self) -> float:
        """
        The current time: the earliest round of the last wavefront, or the ``until`` of the
        last ``run_until`` if later. A device that joins runs its first round from it.
        """
        return self._now

    def next_time(self, sensors: WorldSensors) -> float:
        """Return the earliest pending wakeup timestamp among the devices in ``sensors``."""
        self._sync_membership(sensors)
        return min((self._next_time[dev] for dev in sensors), default=math.inf)

    def last_time_of(self, device: Hashable) -> float:
        """Return the timestamp at which ``device`` last executed a round."""
        return self._last_time[device]

    def step(
        self,
        sensors: WorldSensors,
        neighbors: WorldNeighbors,
        *,
        until: float | None = None,
    ) -> WavefrontStep:
        """
        Select and execute the next concurrent batch of causally independent devices.

        Args:
            sensors: Current sensors of every active device, by device ID.
            neighbors: Current neighbor IDs of every active device, by device ID.
            until: Optional upper timestamp cap beyond which devices are not fired.

        Returns:
            A ``WavefrontStep`` describing the executed concurrent batch.
        """
        self._sync_membership(sensors)
        batch = select_wavefront(
            {dev: self._next_time[dev] for dev in sensors},
            neighbors,
            lookahead=self.clock.period,
            delay=max(self.channel.delay, 0.0 if self.window is None else self.window),
            until=until,
        )
        if not batch:
            return WavefrontStep(time=until or 0.0, devices=(), results={}, outputs={})

        batch_times = {dev: self._next_time[dev] for dev in batch}
        self._now = max(self._now, min(batch_times.values()))
        inboxes = {
            dev: self._gather_inbox(dev, neighbors.get(dev, ()), batch_times[dev])
            for dev in batch
        }
        # The sensors of a device win over the time of its round, as for the other runtimes.
        batch_sensors = {dev: {"time": batch_times[dev], **sensors[dev]} for dev in batch}
        done = self._runner.run(batch_sensors, inboxes.__getitem__, self._states)

        step_results: dict[Hashable, Any] = {}
        step_outputs: dict[Hashable, dict[str, Any]] = {}
        outgoing = self._reverse_edges(batch, neighbors, sensors)
        for dev in batch:
            now = batch_times[dev]
            self._states[dev] = done.states[dev]
            self.results[dev] = step_results[dev] = done.results[dev]
            self.outputs[dev] = step_outputs[dev] = done.outputs[dev]
            self._last_time[dev] = now
            self._transmit(
                outbox=done.outboxes[dev], sender=dev, receivers=outgoing[dev], now=now
            )
            self._next_time[dev] = now + self.clock.interval(self._draws(dev))

        horizon = max(batch_times.values())
        return WavefrontStep(
            time=horizon,
            devices=tuple(batch),
            results=step_results,
            outputs=step_outputs,
        )

    def run_until(
        self,
        until: float,
        sensors: WorldSensors | Callable[[float], WorldSensors],
        neighbors: WorldNeighbors | Callable[[float], WorldNeighbors],
    ) -> dict[Hashable, Any]:
        """
        Advance wavefront batches until every device's next wakeup exceeds ``until``.

        Args:
            until: Target simulation timestamp.
            sensors: Static sensor mapping or callable ``time -> sensors``.
            neighbors: Static neighbor mapping or callable ``time -> neighbors``.

        Returns:
            A copy of the latest results across active devices.
        """
        while True:
            probe_sensors = sensors(0.0) if callable(sensors) else sensors
            earliest = self.next_time(probe_sensors)
            if earliest > until:
                break
            cur_sensors = sensors(earliest) if callable(sensors) else probe_sensors
            cur_neighbors = neighbors(earliest) if callable(neighbors) else neighbors
            executed = self.step(cur_sensors, cur_neighbors, until=until)
            if not executed.devices:
                break
        self._now = max(self._now, until)
        return dict(self.results)

    def reset(self) -> None:
        """Forget all device states, clocks, in-flight messages and outputs."""
        self.results.clear()
        self.outputs.clear()
        self._states.clear()
        self._links.clear()
        self._next_time.clear()
        self._last_time.clear()
        self._device_rngs.clear()
        self._channel_rng = random.Random(f"{self.seed}:channel")
        self._now = 0.0

    def _draws(self, device: Hashable) -> Draws:
        """The randomness of the next round of ``device``, from its own seeded generator."""
        randomness = self._device_rngs.get(device)
        if randomness is None:
            rng = random.Random(f"{self.seed}:dev:{device!r}")
            randomness = self._device_rngs[device] = (rng, rng.random())
        rng, device_draw = randomness
        return Draws(device=device_draw, uniform=rng.random(), exponential=rng.expovariate(1.0))

    def _sync_membership(self, sensors: WorldSensors) -> None:
        active = set(sensors)
        for departed in [dev for dev in self._next_time if dev not in active]:
            self._next_time.pop(departed, None)
            self._last_time.pop(departed, None)
            self._states.pop(departed, None)
            self._links.pop(departed, None)
            self.results.pop(departed, None)
            self.outputs.pop(departed, None)
            for slots in self._links.values():
                slots.pop(departed, None)
        for dev in sensors:
            if dev not in self._next_time:
                self._next_time[dev] = self._now + self.clock.first(self._draws(dev))

    def _gather_inbox(
        self, device: Hashable, peers: Iterable[Hashable], now: float
    ) -> dict[Hashable, dict[str, Any]]:
        slots = self._links.get(device)
        if not slots:
            return {}
        inbox: dict[Hashable, dict[str, Any]] = {}
        for peer in peers:
            slot = slots.get(peer)
            if slot is not None:
                payload = slot.read_at(now, self.channel.retention)
                if payload is not None:
                    inbox[peer] = payload
        return inbox

    def _reverse_edges(
        self,
        batch: Sequence[Hashable],
        neighbors: WorldNeighbors,
        sensors: WorldSensors,
    ) -> dict[Hashable, list[Hashable]]:
        in_batch = set(batch)
        outgoing: dict[Hashable, list[Hashable]] = {dev: [] for dev in batch}
        for receiver in sensors:
            for sender in neighbors.get(receiver, ()):
                if sender != receiver and sender in in_batch:
                    outgoing[sender].append(receiver)
        return outgoing

    def _transmit(
        self,
        *,
        outbox: dict[str, Any],
        sender: Hashable,
        receivers: Sequence[Hashable],
        now: float,
    ) -> None:
        loss = self.channel.loss
        delay = self.channel.delay
        jitter = self.channel.jitter
        for receiver in receivers:
            if loss > 0.0 and self._channel_rng.random() < loss:
                continue
            extra = self._channel_rng.uniform(0.0, jitter) if jitter > 0.0 else 0.0
            slot = self._links.setdefault(receiver, {}).setdefault(sender, _LinkSlot())
            slot.transmit(outbox, now + delay + extra)

"""
Concurrent-wavefront discrete-event runtime: executes batches of causally independent devices
in parallel, spanning event-by-event asynchronous DES and full-system synchronous rounds.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
# In Python 3.14 concurrent.futures loads ThreadPoolExecutor in __getattr__, which astroid misses.
from concurrent.futures import ThreadPoolExecutor  # pylint: disable=no-name-in-module
from dataclasses import dataclass
import math
import random
from typing import Any, Protocol

from phyelds.vm.rounds import Round, run_round

_CHUNKS_PER_WORKER = 4
WorldSensors = Mapping[Hashable, Mapping[str, Any]]
WorldNeighbors = Mapping[Hashable, Iterable[Hashable]]


class Clock(Protocol):
    """Per-device wakeup clock driving asynchronous discrete-event rounds."""

    horizon: float
    """Nominal time span bounding how far ahead of the earliest event a batch looks."""

    def initial_time(self, device: Hashable, rng: random.Random) -> float:
        """Return the timestamp of ``device``'s first round."""

    def next_delta(self, device: Hashable, now: float, rng: random.Random) -> float:
        """Return the positive time increment until ``device``'s next round after ``now``."""


@dataclass(frozen=True)
class PeriodicClock:
    """
    Periodic device clock with optional random initial phase, per-device drift and round jitter.

    With the defaults (``random_phase=False, jitter=0.0, drift=0.0``), every device wakes up
    together at ``0, period, 2 * period, ...``.

    Args:
        period: Nominal interval between two rounds of a device (``> 0``).
        random_phase: Whether each device starts at a uniform random offset in ``(0, period]``.
        jitter: Relative per-round uniform jitter in ``[0.0, 1.0)``.
        drift: Relative per-device clock skew bound in ``[0.0, 1.0)``.

    Raises:
        ValueError: If ``period <= 0`` or ``jitter`` / ``drift`` is outside ``[0.0, 1.0)``.
    """

    period: float = 1.0
    random_phase: bool = False
    jitter: float = 0.0
    drift: float = 0.0

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError(f"period must be positive, not {self.period}")
        if not 0.0 <= self.jitter < 1.0:
            raise ValueError(f"jitter must be in [0.0, 1.0), not {self.jitter}")
        if not 0.0 <= self.drift < 1.0:
            raise ValueError(f"drift must be in [0.0, 1.0), not {self.drift}")

    @property
    def horizon(self) -> float:
        """Nominal lookahead horizon of one period."""
        return float(self.period)

    def initial_time(self, device: Hashable, rng: random.Random) -> float:
        """Draw the initial wakeup time of ``device``."""
        del device
        if not self.random_phase:
            return 0.0
        return float(self.period) * (1.0 - rng.random())

    def next_delta(self, device: Hashable, now: float, rng: random.Random) -> float:
        """Return the next inter-round interval of ``device``."""
        del now
        skew = 1.0
        if self.drift > 0.0:
            skew_rng = random.Random(f"skew:{device!r}")
            skew = 1.0 + skew_rng.uniform(-self.drift, self.drift)
        noise = 1.0 + rng.uniform(-self.jitter, self.jitter) if self.jitter > 0.0 else 1.0
        return max(1e-12, float(self.period) * skew * noise)


class WeibullClock:
    """
    Weibull-distributed inter-round intervals with mean ``period`` (as in Alchemist).

    Args:
        period: Mean interval between two rounds of a device (``> 0``).
        shape: Weibull shape parameter ``k > 0`` (higher values mean more regular periods).
        random_phase: Whether the first round is drawn uniformly in ``(0, period]``.

    Raises:
        ValueError: If ``period <= 0`` or ``shape <= 0``.
    """

    def __init__(
        self, period: float = 1.0, shape: float = 4.0, *, random_phase: bool = True
    ):
        if period <= 0:
            raise ValueError(f"period must be positive, not {period}")
        if shape <= 0:
            raise ValueError(f"shape must be positive, not {shape}")
        self.period = float(period)
        self.horizon = self.period
        self.shape = float(shape)
        self.random_phase = random_phase
        self._scale = self.period / math.gamma(1.0 + 1.0 / self.shape)

    def initial_time(self, device: Hashable, rng: random.Random) -> float:
        """Return the initial wakeup timestamp for ``device``."""
        del device
        if not self.random_phase:
            return 0.0
        return self.period * (1.0 - rng.random())

    def next_delta(self, device: Hashable, now: float, rng: random.Random) -> float:
        """Sample a Weibull interval with mean ``period``."""
        del device, now
        u = min(max(rng.random(), 1e-15), 1.0 - 1e-15)
        return max(1e-12, self._scale * (-math.log(1.0 - u)) ** (1.0 / self.shape))


class ExponentialClock:
    """
    Memoryless Poisson wakeup process with rate ``rate`` rounds per unit time.

    Args:
        rate: Mean firing rate ``lambda > 0``.

    Raises:
        ValueError: If ``rate <= 0``.
    """

    def __init__(self, rate: float = 1.0):
        if rate <= 0:
            raise ValueError(f"rate must be positive, not {rate}")
        self.rate = float(rate)
        self.horizon = 1.0 / self.rate

    def initial_time(self, device: Hashable, rng: random.Random) -> float:
        """Sample the time of the first Poisson event for ``device``."""
        return self.next_delta(device, 0.0, rng)

    def next_delta(self, device: Hashable, now: float, rng: random.Random) -> float:
        """Sample an exponential inter-arrival interval."""
        del device, now
        u = min(max(rng.random(), 1e-15), 1.0 - 1e-15)
        return max(1e-12, -math.log(1.0 - u) / self.rate)


@dataclass(frozen=True)
class Channel:
    """
    Communication channel governing delivery latency, packet loss and message expiry.

    Args:
        delay: Minimum transmission and propagation delay ``>= 0``.
        jitter: Additional uniform delivery delay in ``[0, jitter]``.
        loss: Independent packet drop probability in ``[0.0, 1.0]``.
        retention: Maximum age of a delivered message before a silent neighbor expires;
            ``None`` keeps the latest delivered message while the sender stays a neighbor.
    """

    delay: float = 0.0
    jitter: float = 0.0
    loss: float = 0.0
    retention: float | None = None

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError(f"delay must be non-negative, not {self.delay}")
        if self.jitter < 0:
            raise ValueError(f"jitter must be non-negative, not {self.jitter}")
        if not 0.0 <= self.loss <= 1.0:
            raise ValueError(f"loss must be in [0.0, 1.0], not {self.loss}")
        if self.retention is not None and self.retention <= 0:
            raise ValueError(f"retention must be positive, not {self.retention}")


@dataclass
class _LinkSlot:
    """Committed and in-flight packets on a directed link ``sender -> receiver``."""

    committed: dict[str, Any] | None = None
    committed_at: float = -math.inf
    pending: dict[str, Any] | None = None
    pending_at: float = math.inf

    def transmit(self, payload: dict[str, Any], arrival: float) -> None:
        """Queue ``payload`` arriving at ``arrival``, promoting any earlier arrived packet."""
        if self.pending is not None and self.pending_at <= arrival:
            self.committed = self.pending
            self.committed_at = self.pending_at
        self.pending = payload
        self.pending_at = arrival

    def read_at(self, now: float, retention: float | None) -> dict[str, Any] | None:
        """Return the latest packet delivered by ``now`` and still within ``retention``."""
        if self.pending is not None and self.pending_at <= now:
            self.committed = self.pending
            self.committed_at = self.pending_at
            self.pending = None
            self.pending_at = math.inf
        if self.committed is None:
            return None
        if retention is not None and (now - self.committed_at) > retention:
            return None
        return self.committed


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
        if workers < 1:
            raise ValueError(f"workers must be at least 1, not {workers}")
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
        self._device_rngs: dict[Hashable, random.Random] = {}
        self._channel_rng = random.Random(f"{seed}:channel")

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
        batch = self._select_wavefront(list(sensors), neighbors, until)
        if not batch:
            return WavefrontStep(time=until or 0.0, devices=(), results={}, outputs={})

        batch_times = {dev: self._next_time[dev] for dev in batch}
        inboxes = {
            dev: self._gather_inbox(dev, neighbors.get(dev, ()), batch_times[dev])
            for dev in batch
        }
        rounds = self._execute_batch(batch, sensors, batch_times, inboxes)

        step_results: dict[Hashable, Any] = {}
        step_outputs: dict[Hashable, dict[str, Any]] = {}
        outgoing = self._reverse_edges(batch, neighbors, sensors)
        for dev in batch:
            done = rounds[dev]
            now = batch_times[dev]
            self._states[dev] = done.state
            self.results[dev] = step_results[dev] = done.result
            self.outputs[dev] = step_outputs[dev] = done.outputs
            self._last_time[dev] = now
            self._transmit(outbox=done.outbox, sender=dev, receivers=outgoing[dev], now=now)
            self._next_time[dev] = now + self.clock.next_delta(dev, now, self._rng_for(dev))

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

    def _rng_for(self, device: Hashable) -> random.Random:
        rng = self._device_rngs.get(device)
        if rng is None:
            rng = random.Random(f"{self.seed}:dev:{device!r}")
            self._device_rngs[device] = rng
        return rng

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
                self._next_time[dev] = self.clock.initial_time(dev, self._rng_for(dev))

    def _select_wavefront(
        self,
        devices: Sequence[Hashable],
        neighbors: WorldNeighbors,
        until: float | None,
    ) -> list[Hashable]:
        if not devices:
            return []
        earliest = min(self._next_time[dev] for dev in devices)
        if until is not None and earliest > until:
            return []
        horizon = getattr(self.clock, "horizon", math.inf)
        cap = earliest + horizon
        if until is not None:
            cap = min(cap, until)

        rank = {dev: idx for idx, dev in enumerate(devices)}
        eff_delay = max(self.channel.delay, 0.0 if self.window is None else self.window)
        selected: list[Hashable] = []
        for dev in devices:
            t_dev = self._next_time[dev]
            if t_dev > cap:
                continue
            blocked = False
            for peer in neighbors.get(dev, ()):
                if peer == dev or peer not in rank:
                    continue
                t_peer = self._next_time[peer]
                if t_peer + eff_delay < t_dev or (
                    eff_delay == 0.0 and t_peer == t_dev and rank[peer] < rank[dev]
                ):
                    blocked = True
                    break
            if not blocked:
                selected.append(dev)
        return selected

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

    def _execute_batch(
        self,
        batch: Sequence[Hashable],
        sensors: WorldSensors,
        batch_times: Mapping[Hashable, float],
        inboxes: Mapping[Hashable, Mapping[Hashable, Mapping[str, Any]]],
    ) -> dict[Hashable, Round]:
        def run_one(dev: Hashable) -> tuple[Hashable, Round]:
            dev_sensors = dict(sensors[dev])
            dev_sensors.setdefault("time", batch_times[dev])
            done = run_round(
                self.program, dev, dev_sensors, inboxes[dev], self._states.get(dev), paths="compact"
            )
            return dev, done

        if self.workers == 1 or len(batch) <= 1:
            return dict(run_one(dev) for dev in batch)
        size = max(1, math.ceil(len(batch) / (self.workers * _CHUNKS_PER_WORKER)))
        chunks = [batch[i:i + size] for i in range(0, len(batch), size)]
        with ThreadPoolExecutor(self.workers) as pool:
            parts = list(pool.map(lambda chunk: [run_one(dev) for dev in chunk], chunks))
        return {dev: done for part in parts for dev, done in part}

"""
Time-based aggregate primitives and time-replicated processes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from phyelds import engine
from phyelds.calculus import aggregate, align, exchange, remember, remember_and_evolve
from phyelds.data import NeighborhoodField, StateT
from phyelds.data.codec import register

T = TypeVar("T")


@register
@dataclass(frozen=True)
class _ReplicaTimer:
    """State of the distributed timer driving replica creation."""

    replica_id: int
    spawn_time: float


def local_time() -> float:
    """
    Return the time of the current round, as perceived by the device.

    Returns:
        The value of the device's ``"time"`` sensor.
    """
    return engine.get().node_context.time()


@aggregate
def counter() -> StateT[int]:
    """
    Count the consecutive rounds in which this call runs on the current device.

    Returns:
        The number of rounds so far, this one included: ``1`` on the first round.
    """
    return remember_and_evolve(0, lambda x: x + 1)


@aggregate
def decay(value: float | int, rate: float | int) -> StateT[float | int]:
    """
    Decrease a value by ``rate`` each round, down to ``0``.

    Args:
        value: The starting value; later changes to it are ignored.
        rate: The amount subtracted each round.

    Returns:
        The decayed value, never below ``0``: ``max(0, value - rate)`` on the first
            round when ``value`` is positive, and ``value`` itself when it is not.
    """
    set_value, decay_value = remember(value)
    if decay_value > 0:
        set_value(max(0, decay_value - rate))
    return decay_value


@aggregate
def delta_time(clock: float | None = None) -> float:
    """
    Compute the non-negative time elapsed since the previous round on this device.

    Args:
        clock: Optional timestamp to track. When omitted, ``local_time()`` is used.

    Returns:
        Elapsed time since the last round (``0.0`` on the first round).
    """
    now = float(local_time() if clock is None else clock)
    set_previous, previous = remember(now)
    elapsed = max(0.0, now - float(previous))
    set_previous(now)
    return elapsed


@aggregate
def shared_clock(clock: float | None = None) -> float:
    """
    Synchronize a monotonic shared clock across the network driven by the fastest node.

    Args:
        clock: Optional locally perceived time. Defaults to ``local_time()``.

    Returns:
        The synchronized network timestamp.
    """
    now = float(local_time() if clock is None else clock)
    local_delta = delta_time(now)
    set_clock, clocks = exchange(now)
    local_estimate = float(clocks.local()) + local_delta
    network_max = float(clocks.max())
    synchronized = max(local_estimate, network_max, now)
    set_clock(synchronized)
    return synchronized


def _compute_timer_step(
    remaining: float,
    elapsed: float,
    duration: float,
    periodic: bool,
) -> tuple[float, float]:
    """Return ``(next_stored_remaining, current_time_left)``."""
    time_left = remaining - elapsed
    if periodic and time_left <= 0.0:
        return duration, time_left
    clamped = max(0.0, time_left)
    return clamped, time_left


@aggregate
def timer(
    duration: float,
    *,
    periodic: bool = False,
    clock: float | None = None,
) -> float:
    """
    Count down from ``duration`` using ``clock`` (or ``local_time()`` by default).

    Args:
        duration: Initial countdown duration.
        periodic: If True, resets the timer to ``duration`` for the next round once it
            reaches ``<= 0.0``.
        clock: Optional clock value (e.g. ``shared_clock()``) used to measure elapsed time.

    Returns:
        The time left on the timer (``<= 0.0`` when expired).
    """
    elapsed = delta_time(clock)
    set_remaining, remaining = remember(float(duration))
    next_remaining, time_left = _compute_timer_step(
        float(remaining), elapsed, float(duration), periodic
    )
    set_remaining(next_remaining)
    return time_left


def _step_replica_timer(
    timers: NeighborhoodField[_ReplicaTimer],
    now: float,
    period: float,
) -> _ReplicaTimer:
    """Advance the distributed replica timer and spawn a new replica ID when expired."""
    best: _ReplicaTimer = timers.max(key=lambda t: (t.replica_id, t.spawn_time))
    if now - best.spawn_time >= period:
        return _ReplicaTimer(best.replica_id + 1, now)
    return best


def _evaluate_replica_slots(
    process: Callable[[], T],
    max_replicas: int,
    latest_id: int,
) -> T:
    """Run active replicas in fixed ring-buffer slots to preserve positional alignment."""
    oldest_id = max(0, latest_id - max_replicas + 1)
    active_ids = range(oldest_id, latest_id + 1)
    slot_to_rid = {rid % max_replicas: rid for rid in active_ids}
    results: dict[int, T] = {}
    for slot in range(max_replicas):
        rid = slot_to_rid.get(slot, -1)
        with align(f"slot_{slot}_replica_{rid}"):
            if rid >= 0:
                results[rid] = process()
    return results[oldest_id]


@aggregate
def _run_time_replicated(
    process: Callable[[], T],
    period: float,
    max_replicas: int,
    clock: float | None,
) -> T:
    """Aggregate implementation of time_replicated."""
    now = shared_clock(clock)
    set_timer, timers = exchange(_ReplicaTimer(0, now))
    next_timer = _step_replica_timer(timers, now, period)
    set_timer(next_timer)
    return _evaluate_replica_slots(process, max_replicas, next_timer.replica_id)


def time_replicated(
    process: Callable[[], T],
    period: float,
    *,
    max_replicas: int = 2,
    clock: float | None = None,
) -> T:
    """
    Periodically spawn overlapping replicas of ``process`` to discard obsolete state.

    Each replica with ID ``r`` runs in the fixed positional slot ``r % max_replicas``,
    ensuring alignment stability across rounds as older replicas expire.

    Args:
        process: Zero-argument callable running an aggregate computation.
        period: Time interval between consecutive replica spawns (must be ``> 0``).
        max_replicas: Maximum number of concurrent replicas kept alive (must be ``>= 1``).
        clock: Optional local clock reading passed to ``shared_clock``.

    Returns:
        The result produced by the oldest active replica.

    Raises:
        ValueError: If ``period <= 0`` or ``max_replicas < 1``.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if max_replicas < 1:
        raise ValueError(f"max_replicas must be at least 1, got {max_replicas}")
    return _run_time_replicated(process, float(period), max_replicas, clock)


_UNSET = object()


@aggregate
def delay(value: T, initial: T | None = None) -> T:
    """
    Return the value held by ``value`` in the previous round.

    Args:
        value: Current value to remember for the next round.
        initial: Optional value returned on the very first round. When omitted,
            ``value`` itself is returned on the first round.

    Returns:
        The previous round's value (or ``initial`` on the first round).
    """
    first_value = value if initial is None else initial
    set_previous, previous = remember(first_value)
    old_value: T = previous.value
    set_previous(value)
    return old_value


@aggregate
def has_changed(value: T, *, initially: bool = False) -> bool:
    """
    Return True when ``value`` differs from its value in the previous round.

    Args:
        value: Value to observe across rounds.
        initially: Result returned on the first observation round.

    Returns:
        True if ``value`` changed since the last round, False otherwise.
    """
    set_state, state = remember((_UNSET, False))
    prev_value, initialized = state.value
    changed = initially if not initialized else bool(prev_value != value)
    set_state((value, True))
    return changed


@aggregate
def rising_edge(condition: bool) -> bool:
    """Return True on the round where ``condition`` transitions from False to True."""
    current = bool(condition)
    previous = delay(current, initial=False)
    return current and not previous


@aggregate
def falling_edge(condition: bool) -> bool:
    """Return True on the round where ``condition`` transitions from True to False."""
    current = bool(condition)
    previous = delay(current, initial=False)
    return (not current) and previous


@aggregate
def once(value: T) -> T | None:
    """Return ``value`` on the first round it is evaluated, and ``None`` thereafter."""
    set_done, done = remember(False)
    is_first = not bool(done.value)
    set_done(True)
    return value if is_first else None


@aggregate
def periodic_impulse(period: float, *, clock: float | None = None) -> bool:
    """
    Emit True every ``period`` time units, and False on intermediate rounds.

    Args:
        period: Interval between impulses.
        clock: Optional clock value (defaults to ``local_time()``).

    Returns:
        True when the periodic timer expires in the current round.
    """
    return timer(period, periodic=True, clock=clock) <= 0.0


@aggregate
def recently_true(
    condition: bool,
    duration: float,
    *,
    clock: float | None = None,
) -> bool:
    """
    Return True while ``condition`` is True and for ``duration`` time units after.

    Args:
        condition: Boolean condition to monitor.
        duration: How long the True state persists after ``condition`` becomes False.
        clock: Optional clock value (defaults to ``local_time()``).

    Returns:
        True if ``condition`` held within the last ``duration`` time units.
    """
    elapsed = delta_time(clock)
    set_remaining, remaining = remember(0.0)
    next_remaining = (
        float(duration) if condition else max(0.0, float(remaining.value) - elapsed)
    )
    set_remaining(next_remaining)
    return bool(condition) or next_remaining > 0.0


@aggregate
def _run_exponential_filter(signal: float, alpha: float) -> float:
    """Aggregate implementation of exponential_filter."""
    set_filtered, filtered = remember(float(signal))
    updated = alpha * float(filtered.value) + (1.0 - alpha) * float(signal)
    set_filtered(updated)
    return updated


def exponential_filter(signal: float, alpha: float) -> float:
    """
    Smooth a numeric ``signal`` over time with an exponential moving average.

    Computes ``alpha * previous + (1 - alpha) * signal`` at each round.

    Args:
        signal: Current numeric reading.
        alpha: Smoothing factor in ``[0.0, 1.0]`` (higher retains more history).

    Returns:
        The smoothed signal value.

    Raises:
        ValueError: If ``alpha`` is outside ``[0.0, 1.0]``.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0.0, 1.0], got {alpha}")
    return _run_exponential_filter(signal, float(alpha))

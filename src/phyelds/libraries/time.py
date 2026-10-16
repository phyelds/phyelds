"""
Time-based aggregate primitives and time-replicated processes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from phyelds import engine
from phyelds.calculus import aggregate, align, exchange, remember, remember_and_evolve
from phyelds.data import NeighborhoodField, StateT

T = TypeVar("T")


@dataclass(frozen=True)
class _ReplicaTimer:
    """State of the distributed timer driving replica creation."""

    replica_id: int
    remaining_ttl: float


def local_time() -> float:
    """
    Get the local time of the node.
    :return: the local time of the node.
    """
    return engine.get().node_context.time()


@aggregate
def counter() -> StateT[int]:
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)


@aggregate
def decay(value: float | int, rate: float | int) -> StateT[float | int]:
    """
    Apply a decay function to a value
    :param value: the initial value
    :param rate: the decay rate
    :return: the decayed value
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
    elapsed: float,
    period: float,
) -> _ReplicaTimer:
    """Advance the distributed replica timer and spawn a new replica ID when expired."""
    best: _ReplicaTimer = timers.max(key=lambda t: (t.replica_id, -t.remaining_ttl))
    remaining = best.remaining_ttl - elapsed
    if remaining <= 0.0:
        return _ReplicaTimer(best.replica_id + 1, period)
    return _ReplicaTimer(best.replica_id, remaining)


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
    elapsed = delta_time(shared_clock(clock))
    set_timer, timers = exchange(_ReplicaTimer(0, period))
    next_timer = _step_replica_timer(timers, elapsed, period)
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

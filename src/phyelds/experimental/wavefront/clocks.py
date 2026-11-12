"""
Clocks: when each device runs its rounds, in the time of a wavefront simulation.
"""
from collections.abc import Hashable
from dataclasses import dataclass
import math
import random
from typing import Protocol


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

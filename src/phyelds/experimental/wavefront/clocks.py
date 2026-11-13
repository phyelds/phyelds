"""
Clocks: when each device runs its rounds, in the time of a wavefront simulation.

A clock turns randomness into times. The runtime draws the randomness, and the clock computes
with arithmetic operators only: the same clock works on the floats of one device and on arrays,
such as tensors, holding one value per device.
"""
from dataclasses import dataclass
import math
from typing import Any, Protocol


@dataclass(frozen=True)
class Draws:
    """
    The randomness behind the next round of a device, drawn by the runtime: floats for one
    device, or arrays holding one value per device for many.
    """

    device: Any
    """A uniform draw in ``[0, 1)``, the same for the whole life of a device."""
    uniform: Any
    """A uniform draw in ``[0, 1)``, new at every round."""
    exponential: Any
    """A draw from the exponential distribution of mean 1, new at every round."""


class Clock(Protocol):
    """
    When a device runs its rounds.

    A clock computes its times from ``Draws`` with arithmetic operators only (``+``, ``-``,
    ``*``, ``/``, ``**``), so that it works on floats and on arrays alike, and its times are
    never negative.
    """

    @property
    def period(self) -> float:
        """The mean time between two rounds of a device; a wavefront looks this far ahead."""

    def first(self, draws: Draws) -> Any:
        """The time from when a device joins to its first round."""

    def interval(self, draws: Draws) -> Any:
        """The time from a round of a device to its next one."""


@dataclass(frozen=True)
class PeriodicClock:
    """
    Rounds every ``period``, with a random start, a drift of each device and a jitter of each
    round if asked: with the defaults, every device runs at ``0, period, 2 * period, ...``.

    Args:
        period: The time between two rounds of a device.
        random_phase: Whether a device runs its first round at a uniform time in
            ``(0, period]`` after it joins, rather than right away.
        jitter: How much each interval varies, uniformly, as a fraction of the period.
        drift: How much the period of each device differs, uniformly, as a fraction of it.

    Raises:
        ValueError: If ``period`` is not positive, or ``jitter`` or ``drift`` is not in
            ``[0, 1)``.
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

    def first(self, draws: Draws) -> Any:
        """No time, or a uniform time in ``(0, period]`` with a random phase."""
        return _phase(self.period, self.random_phase, draws)

    def interval(self, draws: Draws) -> Any:
        """The period, stretched by the drift of the device and by the jitter of the round."""
        drift = 1.0 + self.drift * (2.0 * draws.device - 1.0)
        jitter = 1.0 + self.jitter * (2.0 * draws.uniform - 1.0)
        return self.period * drift * jitter


@dataclass(frozen=True)
class WeibullClock:
    """
    Intervals from a Weibull distribution of mean ``period``, as in Alchemist.

    Args:
        period: The mean time between two rounds of a device.
        shape: The shape of the distribution: the higher, the more regular the intervals.
        random_phase: Whether a device runs its first round at a uniform time in
            ``(0, period]`` after it joins, rather than right away.

    Raises:
        ValueError: If ``period`` or ``shape`` is not positive.
    """

    period: float = 1.0
    shape: float = 4.0
    random_phase: bool = True

    def __post_init__(self) -> None:
        if self.period <= 0:
            raise ValueError(f"period must be positive, not {self.period}")
        if self.shape <= 0:
            raise ValueError(f"shape must be positive, not {self.shape}")

    def first(self, draws: Draws) -> Any:
        """No time, or a uniform time in ``(0, period]`` with a random phase."""
        return _phase(self.period, self.random_phase, draws)

    def interval(self, draws: Draws) -> Any:
        """A Weibull interval: the exponential draw, raised to ``1 / shape`` and scaled."""
        scale = self.period / math.gamma(1.0 + 1.0 / self.shape)
        return scale * draws.exponential ** (1.0 / self.shape)


@dataclass(frozen=True)
class ExponentialClock:
    """
    Rounds as the events of a Poisson process: intervals from an exponential distribution
    of mean ``1 / rate``, with no memory of the previous round.

    Args:
        rate: How many rounds a device runs per unit of time, on average.

    Raises:
        ValueError: If ``rate`` is not positive.
    """

    rate: float = 1.0

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError(f"rate must be positive, not {self.rate}")

    @property
    def period(self) -> float:
        """The mean time between two rounds, ``1 / rate``."""
        return 1.0 / self.rate

    def first(self, draws: Draws) -> Any:
        """An exponential time, as for any other round: the process has no memory."""
        return self.interval(draws)

    def interval(self, draws: Draws) -> Any:
        """The exponential draw, scaled to a mean of ``1 / rate``."""
        return draws.exponential / self.rate


def _phase(period: float, random_phase: bool, draws: Draws) -> Any:
    """The time to the first round: uniform in ``(0, period]``, or zero shaped as the draws."""
    if random_phase:
        return period * (1.0 - draws.uniform)
    return draws.uniform * 0.0

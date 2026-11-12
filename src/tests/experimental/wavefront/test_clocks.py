"""
The clocks of a wavefront simulation: when each device runs its rounds, computed from the
randomness the runtime draws, the same way for one device as for an array of them.
"""
import math
import random

import pytest

from phyelds.experimental.wavefront import Draws, ExponentialClock, PeriodicClock, WeibullClock
from tests.experimental.wavefront.arrays import Array


def _draws(device=0.5, uniform=0.5, exponential=1.0):
    return Draws(device=device, uniform=uniform, exponential=exponential)


def test_periodic_clock_runs_every_period_from_time_zero():
    clock = PeriodicClock(2.0)

    assert clock.first(_draws()) == 0.0
    assert clock.interval(_draws()) == 2.0


def test_periodic_clock_with_random_phase_starts_within_the_first_period():
    clock = PeriodicClock(2.0, random_phase=True)

    assert clock.first(_draws(uniform=0.25)) == 1.5


def test_periodic_clock_stretches_its_period_by_the_drift_of_the_device_and_the_jitter():
    clock = PeriodicClock(2.0, jitter=0.1, drift=0.2)

    interval = clock.interval(_draws(device=0.75, uniform=0.0))

    assert interval == pytest.approx(2.0 * 1.1 * 0.9)


def test_weibull_clock_waits_on_average_its_period():
    clock = WeibullClock(2.0, shape=3.0)
    rng = random.Random(1)

    intervals = [clock.interval(_draws(exponential=rng.expovariate(1.0))) for _ in range(20_000)]

    assert sum(intervals) / len(intervals) == pytest.approx(2.0, rel=0.02)


def test_weibull_clock_without_random_phase_starts_at_time_zero():
    clock = WeibullClock(2.0, random_phase=False)

    assert clock.first(_draws()) == 0.0


def test_exponential_clock_waits_an_exponential_time_of_mean_one_over_its_rate():
    clock = ExponentialClock(4.0)

    assert clock.period == 0.25
    assert clock.first(_draws(exponential=2.0)) == 0.5
    assert clock.interval(_draws(exponential=2.0)) == 0.5


@pytest.mark.parametrize(
    "clock",
    [
        PeriodicClock(2.0),
        PeriodicClock(2.0, random_phase=True, jitter=0.1, drift=0.2),
        WeibullClock(2.0, shape=3.0),
        ExponentialClock(4.0),
    ],
)
def test_clocks_compute_on_arrays_of_draws_as_on_floats(clock):
    device, uniform, exponential = [0.1, 0.6], [0.3, 0.9], [0.5, 2.0]
    each = [Draws(*values) for values in zip(device, uniform, exponential)]
    together = Draws(Array(device), Array(uniform), Array(exponential))

    for method in (clock.first, clock.interval):
        assert method(together).values == pytest.approx([method(draws) for draws in each])
        assert all(math.isfinite(value) for value in method(together).values)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PeriodicClock(0.0),
        lambda: PeriodicClock(1.0, jitter=1.0),
        lambda: PeriodicClock(1.0, drift=1.0),
        lambda: WeibullClock(0.0),
        lambda: WeibullClock(1.0, shape=0.0),
        lambda: ExponentialClock(0.0),
    ],
)
def test_clocks_reject_invalid_settings(factory):
    with pytest.raises(ValueError):
        factory()

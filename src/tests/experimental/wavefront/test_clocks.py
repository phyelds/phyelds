"""
The clocks of a wavefront simulation: when each device runs its rounds.
"""
import pytest

from phyelds.experimental.wavefront import ExponentialClock, PeriodicClock, WeibullClock


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

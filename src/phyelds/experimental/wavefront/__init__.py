"""
Wavefront simulation: devices with their own clocks, talking over a channel with delays and
losses, run in batches of devices that do not depend on each other.

With no delay, a wavefront holds devices whose rounds no neighbor can affect, and the results
are those of running the rounds one at a time; with a delay, or with aligned clocks, more
devices run together, up to every device, as in a synchronous round.
"""
from phyelds.experimental.wavefront.channel import Channel
from phyelds.experimental.wavefront.clocks import (
    Clock,
    Draws,
    ExponentialClock,
    PeriodicClock,
    WeibullClock,
)
from phyelds.experimental.wavefront.runtime import WavefrontRuntime, WavefrontStep
from phyelds.experimental.wavefront.schedule import select_wavefront

__all__ = [
    "Channel",
    "Clock",
    "Draws",
    "ExponentialClock",
    "PeriodicClock",
    "WavefrontRuntime",
    "WavefrontStep",
    "WeibullClock",
    "select_wavefront",
]

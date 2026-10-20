"""
Waves: the source pulses every PERIOD rounds, and every pulse travels across the network.

The source spreads how many pulses it sent; a device lights up for a round when the
count it hears changes, which happens later the farther it is. Drag the source and the
waves leave from there.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.spreading import broadcast
from phyelds.libraries.time import has_changed, local_time, recently_true

PERIOD = 6  # rounds between two pulses


@aggregate
def wave() -> bool:
    """Whether a pulse of the source is passing through the device."""
    pulses = broadcast(sense("source"), local_time() // PERIOD)
    return recently_true(has_changed(pulses), 1)

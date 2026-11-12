"""
The channel of a wavefront simulation: when a message arrives, which ones are lost, and for how
long a silent neighbor is still heard.
"""
import pytest

from phyelds.calculus import aggregate, neighbors
from phyelds.experimental.wavefront import Channel, PeriodicClock, WavefrontRuntime
from phyelds.libraries.time import local_time

PAIR = {0: [1], 1: [0]}
APART = {0: [], 1: []}
SENSORS = {0: {}, 1: {}}


@aggregate
def heard_times():
    """The time of the round in which each neighbor sent the message heard."""
    return dict(neighbors(local_time()).exclude_self())


def _rounds_on_aligned_clocks(channel: Channel, topologies: list[dict]) -> list[dict]:
    """The results of the rounds at times 0, 1, 2, ..., one per topology."""
    runtime = WavefrontRuntime(heard_times, clock=PeriodicClock(1.0), channel=channel)
    return [runtime.step(SENSORS, topology).results for topology in topologies]


def test_channel_delivers_a_message_after_its_delay():
    rounds = _rounds_on_aligned_clocks(Channel(delay=0.5), [PAIR, PAIR])

    assert rounds == [{0: {}, 1: {}}, {0: {1: 0.0}, 1: {0: 0.0}}]


def test_channel_keeps_the_last_arrived_message_while_the_next_is_in_flight():
    rounds = _rounds_on_aligned_clocks(Channel(delay=1.5), [PAIR] * 4)

    assert [result[0] for result in rounds] == [{}, {}, {1: 0.0}, {1: 1.0}]


def test_channel_forgets_a_silent_neighbor_after_the_retention():
    topologies = [PAIR, APART, PAIR]

    kept = _rounds_on_aligned_clocks(Channel(delay=0.1), topologies)
    forgotten = _rounds_on_aligned_clocks(Channel(delay=0.1, retention=1.5), topologies)

    assert kept[-1][0] == {1: 0.0}
    assert forgotten[-1][0] == {}


def test_channel_loses_every_message_with_full_loss():
    rounds = _rounds_on_aligned_clocks(Channel(delay=0.1, loss=1.0), [PAIR, PAIR])

    assert rounds[-1] == {0: {}, 1: {}}


@pytest.mark.parametrize(
    "settings",
    [{"delay": -0.1}, {"jitter": -0.1}, {"loss": 1.2}, {"retention": 0.0}],
)
def test_channel_rejects_invalid_settings(settings):
    with pytest.raises(ValueError):
        Channel(**settings)

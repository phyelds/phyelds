"""
The channel of a wavefront simulation: when a message arrives, which ones are lost, and for how
long a silent neighbor is still heard, computed from the randomness the runtime draws.
"""
import pytest

from phyelds.calculus import aggregate, neighbors
from phyelds.experimental.wavefront import Channel, PeriodicClock, WavefrontRuntime
from phyelds.libraries.time import local_time
from tests.experimental.wavefront.arrays import Array

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


def test_channel_delays_a_message_by_its_delay_and_a_share_of_its_jitter():
    channel = Channel(delay=0.5, jitter=0.2)

    assert channel.arrival(1.0, 0.5) == pytest.approx(1.6)


def test_channel_loses_a_message_whose_draw_falls_below_the_loss():
    channel = Channel(loss=0.25)

    assert channel.lost(0.2)
    assert not channel.lost(0.3)
    assert not Channel().lost(0.0)


def test_channel_hears_a_delivered_message_until_the_retention():
    channel = Channel(retention=1.0)

    assert channel.heard(0.5)
    assert not channel.heard(1.5)
    assert not channel.heard(-0.1)  # not delivered yet
    assert Channel().heard(100.0)


@pytest.mark.parametrize(
    "channel", [Channel(), Channel(delay=0.5, jitter=0.2, loss=0.25, retention=1.0)]
)
def test_channel_computes_on_arrays_of_draws_as_on_floats(channel):
    sent, uniform, ages = [1.0, 2.0, 3.0], [0.1, 0.5, 0.9], [-0.1, 0.5, 1.5]

    arrivals = channel.arrival(Array(sent), Array(uniform))
    losses = channel.lost(Array(uniform))
    heard = channel.heard(Array(ages))

    assert arrivals.values == pytest.approx([channel.arrival(*pair) for pair in zip(sent, uniform)])
    assert losses.values == [channel.lost(draw) for draw in uniform]
    assert heard.values == [channel.heard(age) for age in ages]


@pytest.mark.parametrize(
    "settings",
    [{"delay": -0.1}, {"jitter": -0.1}, {"loss": 1.2}, {"retention": 0.0}],
)
def test_channel_rejects_invalid_settings(settings):
    with pytest.raises(ValueError):
        Channel(**settings)

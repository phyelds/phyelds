"""
Wavefronts of a batch of devices on a torch device: the rule that picks them, and the rounds
they run, as the wavefront runtime of phyelds computes them.
"""
import math
import random

import pytest
import torch

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.experimental.wavefront import (
    Channel,
    PeriodicClock,
    WavefrontRuntime,
    WeibullClock,
    select_wavefront,
)
from phyelds.gpu import (
    BatchSynchronousRuntime,
    BatchWavefrontRuntime,
    GraphTopology,
    radius_topology,
    select_batch,
)
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time
from phyelds.vm.asynchronous import AsynchronousRuntime

COUNT = 40
PAIR = {0: [1], 1: [0]}
ONE_WAY = {0: [1, 2], 1: [0], 2: [1, 3], 3: [2], 4: [3]}  # 4 hears 3, 3 does not hear 4
CHANNELS = [
    Channel(delay=0.5),
    Channel(delay=1.5),
    Channel(delay=0.1, retention=0.5),
    Channel(delay=0.1, retention=1.5),
    Channel(delay=0.1, loss=1.0),
]
CHANNEL_IDS = ["delay", "in flight", "expired", "retained", "lost"]


@aggregate
def libraries():
    potential = distance_to(sense("source"))
    store("potential", potential)
    return potential, gossip_max(local_id()), count_nodes(potential)


@aggregate
def heard_times():
    return neighbors(local_time()).sum(include_self=False)


@aggregate
def addressed():
    ids = neighbors(local_id())
    _, received, send = exchange(0)
    send(received + ids)  # each neighbor gets its own entry, or the id of the sender
    return received.sum()


@aggregate
def rounds():
    count, set_count = remember(0)
    return set_count(count + 1)


def _graph(device: str = "cpu"):
    rng = random.Random(5)
    positions = [(rng.uniform(0.0, 5.0), rng.uniform(0.0, 5.0)) for _ in range(COUNT)]
    topology = radius_topology(torch.tensor(positions, dtype=torch.float64, device=device), 1.5)
    sensors = {"source": torch.arange(COUNT, device=device) == 0}
    return topology, sensors


@pytest.mark.parametrize("seed", range(20))
def test_select_batch_picks_the_devices_select_wavefront_picks(seed):
    rng = random.Random(seed)
    topology, _ = _graph()
    times = [round(rng.uniform(0.0, 2.0), 1) for _ in range(COUNT)]  # rounded: ties happen
    delay = rng.choice([0.0, 0.0, 0.1, 0.5])
    until = rng.choice([None, 1.0])

    batch = select_batch(
        torch.tensor(times, dtype=torch.float64), topology, lookahead=1.0, delay=delay, until=until
    )

    expected = select_wavefront(
        dict(enumerate(times)), topology.to_neighbors(), lookahead=1.0, delay=delay, until=until
    )
    assert batch.tolist() == expected


def _plain(value, index):
    """The value of device ``index`` in ``value``, as Python values; NaN is ``None``."""
    if isinstance(value, tuple):
        return tuple(_plain(item, index) for item in value)
    if isinstance(value, torch.Tensor):
        item = value[index].item()
        return None if isinstance(item, float) and math.isnan(item) else item
    return value


def _latest(results, index):
    """The latest result of device ``index``, from rows ``(values, held)`` of every device."""
    if isinstance(results, tuple) and not isinstance(results[0], torch.Tensor):
        return tuple(_latest(item, index) for item in results)
    values, held = results
    return _plain(values, index) if bool(held[index]) else None


def test_batch_wavefront_runs_every_device_together_on_aligned_clocks_with_a_delay():
    topology, sensors = _graph()
    wavefront = BatchWavefrontRuntime(
        libraries, topology, clock=PeriodicClock(1.0), channel=Channel(delay=0.01)
    )
    synchronous = BatchSynchronousRuntime(libraries, topology)

    for _ in range(6):
        step = wavefront.step(sensors)
        expected = synchronous.run_round(sensors)

        assert step.devices.tolist() == list(range(COUNT))
        assert [_plain(step.results, index) for index in range(COUNT)] == [
            _plain(expected, index) for index in range(COUNT)
        ]


@pytest.mark.parametrize("program", [libraries, addressed], ids=lambda program: program.__name__)
def test_batch_wavefront_without_delay_matches_the_rounds_run_one_at_a_time(program):
    topology, sensors = _graph()
    clock = PeriodicClock(1.0, random_phase=True, jitter=0.1, drift=0.1)
    wavefront = BatchWavefrontRuntime(program, topology, clock=clock, seed=3)
    schedule, sizes = [], []
    while wavefront.next_time() <= 6.0:
        step = wavefront.step(sensors, until=6.0)
        sizes.append(step.devices.numel())
        schedule += [(wavefront.last_times[device].item(), device) for device in step.devices.tolist()]

    one_at_a_time = AsynchronousRuntime(program)
    neighbors_of = topology.to_neighbors()
    expected = {}
    for when, device in sorted(schedule):
        expected[device] = one_at_a_time.spike(
            device, {"source": device == 0, "time": when}, neighbors_of[device]
        )

    assert max(sizes) > 1
    assert {device: _latest(wavefront.results, device) for device in expected} == expected


@pytest.mark.parametrize("channel", CHANNELS, ids=CHANNEL_IDS)
def test_batch_wavefront_delivers_messages_as_the_wavefront_runtime_does(channel):
    on_cpu = WavefrontRuntime(heard_times, clock=PeriodicClock(1.0), channel=channel)
    batch = BatchWavefrontRuntime(
        heard_times, GraphTopology.from_neighbors(PAIR), clock=PeriodicClock(1.0), channel=channel
    )

    for _ in range(4):
        expected = on_cpu.step({0: {}, 1: {}}, PAIR).results
        step = batch.step({})

        assert {device: _plain(step.results, device) for device in PAIR} == expected


@pytest.mark.parametrize("channel", CHANNELS, ids=CHANNEL_IDS)
def test_batch_wavefront_delivers_fields_as_the_wavefront_runtime_does(channel):
    on_cpu = WavefrontRuntime(addressed, clock=PeriodicClock(1.0), channel=channel)
    batch = BatchWavefrontRuntime(
        addressed, GraphTopology.from_neighbors(ONE_WAY), clock=PeriodicClock(1.0),
        channel=channel,
    )

    for _ in range(5):
        expected = on_cpu.step({device: {} for device in ONE_WAY}, ONE_WAY).results
        step = batch.step({})

        assert {device: _plain(step.results, device) for device in ONE_WAY} == expected


def test_batch_wavefront_runs_weibull_clocks_over_a_lossy_channel():
    topology, sensors = _graph()
    wavefront = BatchWavefrontRuntime(
        rounds, topology, clock=WeibullClock(1.0, shape=3.0),
        channel=Channel(delay=0.02, jitter=0.01, loss=0.1), window=0.05, seed=5,
    )

    values, held = wavefront.run_until(4.0, sensors)

    assert bool(held.all())
    assert bool((values >= 2).all())
    assert wavefront.time == 4.0


def test_batch_wavefront_rejects_a_negative_window():
    topology, _ = _graph()

    with pytest.raises(ValueError, match="window"):
        BatchWavefrontRuntime(rounds, topology, window=-0.1)

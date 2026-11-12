"""
Tests for WavefrontRuntime: concurrent batches of causally independent devices, bridging
event-by-event asynchronous DES and full-system synchronous rounds.
"""
import pytest

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time
from phyelds.vm.asynchronous import AsynchronousRuntime
from phyelds.vm.synchronous import SynchronousRuntime
from phyelds.vm.wavefront import (
    Channel,
    ExponentialClock,
    PeriodicClock,
    WavefrontRuntime,
    WeibullClock,
)


@aggregate
def gradient_leader_count():
    potential = distance_to(sense("source"))
    store("potential", potential)
    return potential, gossip_max(local_id()), count_nodes(potential)


@aggregate
def heard_times():
    return dict(neighbors(local_time()).exclude_self())


@aggregate
def round_counter():
    count, set_count = remember(0)
    return set_count(count + 1)


def _grid(width: int, height: int) -> dict[int, list[int]]:
    return {
        x * height + y: [
            ox * height + oy
            for ox in range(max(0, x - 1), min(width, x + 2))
            for oy in range(max(0, y - 1), min(height, y + 2))
            if (ox, oy) != (x, y)
        ]
        for x in range(width)
        for y in range(height)
    }


def _sensors(topology: dict[int, list[int]]) -> dict[int, dict[str, object]]:
    return {device: {"source": device == 0} for device in topology}


def test_wavefront_with_zero_delay_matches_sequential_des_while_batching():
    topology = _grid(5, 4)
    sensors = _sensors(topology)
    clock = PeriodicClock(1.0, random_phase=True)
    wavefront = WavefrontRuntime(
        gradient_leader_count, clock=clock, channel=Channel(delay=0.0), seed=7
    )
    sequential = AsynchronousRuntime(gradient_leader_count)

    # Extract exact wakeup schedule from a matching clock seed for single-event reference.
    probe = WavefrontRuntime(round_counter, clock=clock, seed=7)
    events: list[tuple[float, int]] = []
    while True:
        step = probe.step(sensors, topology)
        if step.time > 10.0:
            break
        for dev in step.devices:
            events.append((probe.last_time_of(dev), dev))
    events.sort()

    expected_final: dict[int, object] = {}
    for when, dev in events:
        if when <= 10.0:
            expected_final[dev] = sequential.spike(dev, {**sensors[dev], "time": when}, topology[dev])

    batch_sizes: list[int] = []
    while wavefront.next_time(sensors) <= 10.0:
        batch = wavefront.step(sensors, topology)
        batch_sizes.append(len(batch.devices))

    assert max(batch_sizes) > 1
    assert sum(batch_sizes) / len(batch_sizes) > 1.5
    assert wavefront.results == expected_final
    assert wavefront.outputs == sequential.outputs


def test_wavefront_matches_sequential_spikes_at_every_horizon():
    topology = _grid(4, 3)
    sensors = _sensors(topology)
    clock = PeriodicClock(1.0, random_phase=True, drift=0.05, jitter=0.05)
    wavefront = WavefrontRuntime(gradient_leader_count, clock=clock, seed=13, workers=2)
    sequential = AsynchronousRuntime(gradient_leader_count)

    schedule_probe = WavefrontRuntime(round_counter, clock=clock, seed=13)
    scheduled: list[tuple[float, int]] = []
    while schedule_probe.next_time(sensors) <= 8.0:
        step = schedule_probe.step(sensors, topology)
        for dev in step.devices:
            scheduled.append((schedule_probe.last_time_of(dev), dev))
    scheduled.sort()

    expected_results: dict[int, object] = {}
    idx = 0
    for horizon in range(1, 9):
        while idx < len(scheduled) and scheduled[idx][0] <= float(horizon):
            when, dev = scheduled[idx]
            expected_results[dev] = sequential.spike(
                dev, {**sensors[dev], "time": when}, topology[dev]
            )
            idx += 1
        actual = wavefront.run_until(float(horizon), sensors, topology)
        assert actual == expected_results
        assert wavefront.outputs == sequential.outputs


def test_wavefront_collapses_to_full_system_synchronous_batches_in_worst_case():
    topology = _grid(5, 4)
    sensors = _sensors(topology)
    wavefront = WavefrontRuntime(
        gradient_leader_count,
        clock=PeriodicClock(1.0, random_phase=False),
        channel=Channel(delay=0.01),
    )
    synchronous = SynchronousRuntime(gradient_leader_count)

    for round_index in range(10):
        step = wavefront.step(sensors, topology)
        expected = synchronous.run_round(
            {dev: {**sensors[dev], "time": float(round_index)} for dev in topology},
            topology,
        )
        assert len(step.devices) == len(topology)
        assert step.results == expected
        assert wavefront.outputs == synchronous.outputs


def test_wavefront_channel_models_in_flight_latency_loss_and_retention():
    topology = {0: [1], 1: [0]}
    sensors = {0: {}, 1: {}}
    # Node 0 wakes at 0.0, 1.0; node 1 wakes at 0.2, 0.7, 1.2 through custom clock
    times = {0: [0.0, 1.0, 5.0], 1: [0.2, 0.7, 1.2, 3.0]}
    cursors = {0: 0, 1: 0}

    class ScriptedClock:
        def initial_time(self, device, _rng):
            cursors[device] = 1
            return times[device][0]

        def next_delta(self, device, now, _rng):
            idx = cursors[device]
            cursors[device] = idx + 1
            return times[device][idx] - now if idx < len(times[device]) else 10.0

    # Delay 0.5, retention 1.0:
    # - Wavefront 1: 0 @ 0.0 and 1 @ 0.2 are concurrent (|0.2 - 0.0| < 0.5) -> both hear {}
    # - Wavefront 2: 1 @ 0.7 and 0 @ 1.0 are concurrent (0.7 + 0.5 > 1.0) ->
    #   1 hears 0's 0.0 packet (arrived 0.5), 0 hears 1's 0.2 packet (arrived 0.7)
    # - Wavefront 3: 1 @ 1.2 blocks 0 @ 5.0; 0's 1.0 packet (arrives 1.5) is still in flight,
    #   so 1 still reads committed 0.0
    # - Wavefront 4: 1 @ 3.0 blocks 0 @ 5.0; 0's 1.0 packet arrived at 1.5, age 1.5 > 1.0 -> {}
    runtime = WavefrontRuntime(
        heard_times,
        clock=ScriptedClock(),
        channel=Channel(delay=0.5, retention=1.0),
    )

    assert runtime.step(sensors, topology).results == {0: {}, 1: {}}
    assert runtime.step(sensors, topology).results == {0: {1: 0.2}, 1: {0: 0.0}}
    assert runtime.step(sensors, topology).results == {1: {0: 0.0}}
    assert runtime.step(sensors, topology).results == {1: {}}

    lossy = WavefrontRuntime(
        heard_times,
        clock=PeriodicClock(1.0, random_phase=False),
        channel=Channel(delay=0.01, loss=1.0),
    )
    lossy.step(sensors, topology)
    assert lossy.step(sensors, topology).results == {0: {}, 1: {}}


def test_weibull_and_exponential_clocks_and_callable_world_and_reset():
    topology = {0: [1], 1: [0]}
    weibull_rt = WavefrontRuntime(
        round_counter,
        clock=WeibullClock(period=1.0, shape=3.0),
        channel=Channel(delay=0.02, jitter=0.01, loss=0.1),
        window=0.05,
        seed=5,
    )
    results = weibull_rt.run_until(
        4.0,
        lambda t: {0: {"t": t}, 1: {"t": t}},
        lambda _t: topology,
    )
    assert all(count >= 2 for count in results.values())

    weibull_sync_phase = WeibullClock(period=1.0, shape=2.0, random_phase=False)
    exp_rt = WavefrontRuntime(round_counter, clock=ExponentialClock(rate=2.0), seed=3)
    assert exp_rt.run_until(2.0, {0: {}, 1: {}}, topology)
    exp_rt.reset()
    assert exp_rt.results == {}
    assert weibull_sync_phase.initial_time(0, None) == 0.0  # type: ignore[arg-type]

    # Device leaving after exchanging messages cleans up link slots, and self/unknown peers work.
    leaving = WavefrontRuntime(heard_times, clock=PeriodicClock(1.0), channel=Channel(delay=0.01))
    leaving.step({0: {}, 1: {}}, {0: [0, 1, 99], 1: [0]})
    leaving.step({0: {}, 1: {}}, {0: [1], 1: [0]})
    assert leaving.step({0: {}}, {0: []}).results == {0: {}}
    assert leaving.step({}, {}).devices == ()
    assert leaving.step({0: {}}, {0: []}, until=-1.0).devices == ()
    assert leaving.run_until(10.0, lambda t: {} if t > 0 else {0: {}}, {0: []}) == {}

    # Packet still in flight when receiver has no prior committed packet from sender.
    in_flight_first = WavefrontRuntime(
        heard_times, clock=PeriodicClock(1.0), channel=Channel(delay=2.5)
    )
    in_flight_first.step({0: {}, 1: {}}, {0: [1], 1: [0]})
    assert in_flight_first.step({0: {}, 1: {}}, {0: [1], 1: [0]}).results[1] == {}


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PeriodicClock(0.0),
        lambda: PeriodicClock(1.0, jitter=1.0),
        lambda: PeriodicClock(1.0, drift=1.0),
        lambda: WeibullClock(0.0),
        lambda: WeibullClock(1.0, shape=0.0),
        lambda: ExponentialClock(0.0),
        lambda: Channel(delay=-0.1),
        lambda: Channel(jitter=-0.1),
        lambda: Channel(loss=1.2),
        lambda: Channel(retention=0.0),
        lambda: WavefrontRuntime(round_counter, window=-0.1),
        lambda: WavefrontRuntime(round_counter, workers=0),
    ],
)
def test_wavefront_validates_configuration_parameters(factory):
    with pytest.raises(ValueError):
        factory()

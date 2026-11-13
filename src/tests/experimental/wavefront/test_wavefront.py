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
from phyelds.experimental.wavefront import (
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


def test_wavefront_runtime_matches_sequential_spikes_while_batching_without_delay():
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


def test_wavefront_runtime_matches_sequential_spikes_at_every_run_until():
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


def test_wavefront_runtime_matches_synchronous_rounds_on_aligned_clocks_with_delay():
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


def test_wavefront_runtime_runs_rounds_on_weibull_clocks_over_a_lossy_channel():
    topology = {0: [1], 1: [0]}
    runtime = WavefrontRuntime(
        round_counter,
        clock=WeibullClock(period=1.0, shape=3.0),
        channel=Channel(delay=0.02, jitter=0.01, loss=0.1),
        window=0.05,
        seed=5,
    )

    results = runtime.run_until(
        4.0,
        lambda t: {0: {"t": t}, 1: {"t": t}},
        lambda _t: topology,
    )

    assert all(count >= 2 for count in results.values())


def test_wavefront_runtime_forgets_every_device_on_reset():
    runtime = WavefrontRuntime(round_counter, clock=ExponentialClock(rate=2.0), seed=3)
    ran = runtime.run_until(2.0, {0: {}, 1: {}}, {0: [1], 1: [0]})

    runtime.reset()

    assert ran
    assert runtime.results == {}


def test_wavefront_runtime_forgets_a_device_that_leaves_with_its_messages():
    runtime = WavefrontRuntime(heard_times, clock=PeriodicClock(1.0), channel=Channel(delay=0.01))
    runtime.step({0: {}, 1: {}}, {0: [0, 1, 99], 1: [0]})  # itself and unknown 99 are ignored
    runtime.step({0: {}, 1: {}}, {0: [1], 1: [0]})

    alone = runtime.step({0: {}}, {0: []})

    assert alone.results == {0: {}}


def test_wavefront_runtime_runs_nothing_without_devices_or_rounds_due_by_until():
    runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0))
    runtime.step({0: {}}, {0: []})

    assert runtime.step({}, {}).devices == ()
    assert runtime.step({0: {}}, {0: []}, until=-1.0).devices == ()


def test_wavefront_runtime_forgets_the_devices_that_leave_the_world_during_a_run():
    runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0))
    runtime.step({0: {}}, {0: []})

    results = runtime.run_until(10.0, lambda t: {} if t > 0 else {0: {}}, {0: []})

    assert results == {}


@pytest.mark.parametrize(
    "factory",
    [
        lambda: WavefrontRuntime(round_counter, window=-0.1),
        lambda: WavefrontRuntime(round_counter, workers=0),
    ],
)
def test_wavefront_runtime_rejects_invalid_settings(factory):
    with pytest.raises(ValueError):
        factory()


def test_wavefront_runtime_draws_the_drift_of_each_device_from_its_seed():
    topology = {0: [], 1: []}

    def last_round_times(seed):
        runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0, drift=0.5), seed=seed)
        runtime.run_until(10.0, _sensors(topology), topology)
        return [runtime.last_time_of(device) for device in topology]

    assert last_round_times(1) == last_round_times(1)
    assert last_round_times(1) != last_round_times(2)


def test_wavefront_runtime_starts_a_joining_device_from_the_current_time():
    runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0))
    runtime.run_until(5.0, {0: {}}, {0: []})

    runtime.step({0: {}, 1: {}}, {0: [], 1: []})

    assert runtime.last_time_of(1) >= 5.0


def test_wavefront_runtime_keeps_the_time_of_its_last_wavefront_or_run():
    runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0))

    runtime.step({0: {}}, {0: []})
    runtime.step({0: {}}, {0: []})
    after_steps = runtime.time
    runtime.run_until(4.5, {0: {}}, {0: []})

    assert after_steps == 1.0
    assert runtime.time == 4.5


def test_wavefront_runtime_keeps_a_device_that_joins_during_a_run():
    topology = {0: [], 1: []}

    def sensors_at(time):
        return {0: {}, 1: {}} if time >= 2.0 else {0: {}}

    runtime = WavefrontRuntime(round_counter, clock=PeriodicClock(1.0))

    results = runtime.run_until(6.0, sensors_at, lambda _time: topology)

    assert results == {0: 7, 1: 5}  # device 1 runs at 2, 3, 4, 5 and 6

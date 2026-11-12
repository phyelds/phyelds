"""
Rounds run by hand: the result, messages, state and outputs that the round of one device, or
the rounds of many, leave behind.
"""
import pytest

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import local_id, sense, store
from phyelds.vm.internal import MutableEngine
from phyelds.vm.rounds import RoundRunner, run_round


@aggregate
def counter():
    count, set_count = remember(0)
    return set_count(count + 1)


@aggregate
def neighbor_ids():
    return sorted(neighbors(local_id()).exclude_self().values())


@aggregate
def stored_sensor():
    store("seen", sense("temperature"))
    return None


def test_run_round_unwraps_a_state_result():
    done = run_round(counter, 0, {}, {})

    assert done.result == 1


def test_run_round_continues_from_the_state_of_the_previous_round():
    first = run_round(counter, 0, {}, {})

    second = run_round(counter, 0, {}, {}, first.state)

    assert second.result == 2


def test_run_round_reads_the_messages_of_the_inbox():
    sent = {device: run_round(neighbor_ids, device, {}, {}).outbox for device in (1, 2)}

    done = run_round(neighbor_ids, 0, {}, sent)

    assert done.result == [1, 2]


def test_run_round_collects_the_outputs_from_the_sensors():
    done = run_round(stored_sensor, 0, {"temperature": 21.5}, {})

    assert done.outputs == {"seen": 21.5}


def test_run_round_with_compact_paths_keys_the_messages_by_integers():
    done = run_round(neighbor_ids, 0, {}, {}, paths="compact")

    assert all(isinstance(key, int) for key in done.outbox)


def _no_messages(_device):
    return {}


def test_round_runner_runs_each_device_with_its_own_inbox():
    sent = {
        device: run_round(neighbor_ids, device, {}, {}, paths="compact").outbox
        for device in (1, 2)
    }
    inboxes = {0: {1: sent[1], 2: sent[2]}, 3: {2: sent[2]}}
    runner = RoundRunner(neighbor_ids)

    done = runner.run({0: {}, 3: {}}, inboxes.__getitem__, {})

    assert done.results == {0: [1, 2], 3: [2]}


def test_round_runner_continues_each_device_from_its_state():
    runner = RoundRunner(counter)
    first = runner.run({0: {}, 1: {}}, _no_messages, {})

    second = runner.run({0: {}, 1: {}}, _no_messages, {0: first.states[0]})

    assert second.results == {0: 2, 1: 1}


def test_round_runner_collects_the_outboxes_and_outputs_of_each_device():
    runner = RoundRunner(stored_sensor)

    done = runner.run({0: {"temperature": 20.0}, 1: {"temperature": 21.5}}, _no_messages, {})

    assert done.outputs == {0: {"seen": 20.0}, 1: {"seen": 21.5}}
    assert list(done.outboxes) == [0, 1]


def test_round_runner_computes_the_same_rounds_in_worker_threads():
    sensors = {device: {"temperature": float(device)} for device in range(40)}

    sequential = RoundRunner(stored_sensor).run(sensors, _no_messages, {})
    threaded = RoundRunner(stored_sensor, workers=4).run(sensors, _no_messages, {})

    assert threaded == sequential
    assert list(threaded.outputs) == list(sensors)


def test_round_runner_builds_one_engine_on_the_calling_thread():
    built = []

    def factory():
        built.append(1)
        return MutableEngine(paths="compact")

    runner = RoundRunner(counter, engine_factory=factory)

    runner.run({0: {}}, _no_messages, {})
    runner.run({0: {}}, _no_messages, {})

    assert len(built) == 1


def test_round_runner_rejects_fewer_than_one_worker():
    with pytest.raises(ValueError, match="at least 1"):
        RoundRunner(counter, workers=0)

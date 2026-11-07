"""
A round of one device, run by hand: the result, messages, state and outputs it leaves behind.
"""
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import local_id, sense, store
from phyelds.vm.rounds import run_round


@aggregate
def counter():
    set_count, count = remember(0)
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

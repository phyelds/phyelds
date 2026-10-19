"""The histories of collective state machines, against the definitions of the paper."""
from math import inf

from phyelds.experimental.state_machines import Next, _extend, _forget, _merge, _MachineHistory

WAIT, WANDER, SOLVE, DEFEND = range(4)


def _history(*entries, forgotten: int = 0) -> _MachineHistory:
    return _MachineHistory(forgotten, tuple(entries))


def test_extension_appends_after_a_transition():
    history = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0))

    extended = _extend(history, Next(WANDER), now=2.0)

    assert extended == _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (-inf, WANDER, 2.0))


def test_extension_replaces_a_final_self_loop():
    history = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (-inf, WANDER, 2.0))

    extended = _extend(history, Next(SOLVE, 100), now=3.0)

    assert extended == _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 3.0))


def test_maximum_of_example_3_is_the_history_that_defends():
    solved = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 2.0), (10, WAIT, 3.0))
    defended = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (inf, DEFEND, 2.0))

    assert _merge([solved, defended]) == defended


def test_maximum_prefers_a_longer_history_to_its_prefix():
    prefix = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0))
    longer = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 2.0))

    assert _merge([longer, prefix]) == longer


def test_maximum_aligns_forgotten_entries_and_takes_the_earliest_time():
    # the second forgot WAIT, and entered WANDER later: the two are compatible
    first = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0))
    second = _history((10, WANDER, 4.0), (100, SOLVE, 5.0), forgotten=1)

    assert _merge([first, second]) == _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 5.0))


def test_maximum_discards_the_smaller_history_at_the_first_incompatible_entry():
    # the first forgot what the third remembers: they are compatible, the second is not
    first = _history((inf, DEFEND, 2.0), forgotten=2)
    second = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 2.0))
    third = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0))

    assert _merge([first, second, third]) == _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (inf, DEFEND, 2.0))


def test_maximum_keeps_all_forgotten_when_every_history_forgot():
    first = _history((10, WANDER, 1.0), (100, SOLVE, 2.0), forgotten=1)
    second = _history((100, SOLVE, 2.0), forgotten=2)

    assert _merge([first, second]) == _history((10, WANDER, 1.0), (100, SOLVE, 2.0), forgotten=1)


def test_forgetting_drops_the_entries_older_than_the_window():
    history = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (100, SOLVE, 8.0), (-inf, SOLVE, 9.0))

    assert _forget(history, now=9.0, window=5.0) == _history((100, SOLVE, 8.0), (-inf, SOLVE, 9.0), forgotten=2)


def test_forgetting_keeps_at_least_two_entries():
    history = _history((-inf, WAIT, 0.0), (10, WANDER, 1.0), (-inf, WANDER, 2.0))

    assert _forget(history, now=100.0, window=5.0) == _history((10, WANDER, 1.0), (-inf, WANDER, 2.0), forgotten=1)

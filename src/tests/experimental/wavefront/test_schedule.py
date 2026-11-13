"""
The rule that picks a wavefront: the devices whose next round no neighbor can still affect.
"""
import math

from phyelds.experimental.wavefront import select_wavefront

LINE = {0: [1], 1: [0, 2], 2: [1]}


def test_select_wavefront_runs_the_devices_due_before_their_neighbors_without_delay():
    next_times = {0: 0.3, 1: 0.5, 2: 0.1}

    batch = select_wavefront(next_times, LINE, lookahead=1.0, delay=0.0)

    assert batch == [0, 2]


def test_select_wavefront_runs_first_the_device_listed_first_on_a_tie_without_delay():
    next_times = {0: 0.5, 1: 0.5, 2: 0.5}

    batch = select_wavefront(next_times, LINE, lookahead=1.0, delay=0.0)

    assert batch == [0]  # 2 waits for 1, which waits for 0


def test_select_wavefront_runs_together_the_neighbors_closer_than_the_delay():
    next_times = {0: 0.0, 1: 0.2, 2: 0.4}

    batch = select_wavefront(next_times, LINE, lookahead=1.0, delay=0.25)

    assert batch == [0, 1, 2]


def test_select_wavefront_holds_a_device_whose_neighbor_message_arrives_at_its_round():
    next_times = {0: 0.0, 1: 0.5}

    batch = select_wavefront(next_times, {0: [1], 1: [0]}, lookahead=1.0, delay=0.5)

    assert batch == [0]


def test_select_wavefront_holds_the_devices_past_the_lookahead():
    next_times = {0: 0.0, 2: 1.5}

    batch = select_wavefront(next_times, {}, lookahead=1.0, delay=0.0)

    assert batch == [0]


def test_select_wavefront_holds_the_devices_past_until():
    next_times = {0: 0.0, 2: 0.5}

    assert select_wavefront(next_times, {}, lookahead=1.0, delay=0.0, until=0.25) == [0]
    assert select_wavefront(next_times, {}, lookahead=1.0, delay=0.0, until=-1.0) == []


def test_select_wavefront_ignores_the_neighbors_with_no_pending_round():
    next_times = {1: 0.5}

    batch = select_wavefront(next_times, LINE, lookahead=math.inf, delay=0.0)

    assert batch == [1]


def test_select_wavefront_picks_nothing_without_devices():
    assert not select_wavefront({}, {}, lookahead=1.0, delay=0.0)

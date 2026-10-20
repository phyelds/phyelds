"""Keeps the Python side of the browser playground working, outside the browser."""
import importlib.util
import math
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[3] / "docs" / "playground" / "runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("playground_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


# ---------- watching expressions ----------

def _span(code: str, text: str, occurrence: int = 0) -> tuple[int, int]:
    """Where the `occurrence`-th `text` is in `code`, in UTF-16 units, as the editor counts."""
    index = -1
    for _ in range(occurrence + 1):
        index = code.index(text, index + 1)
    start = len(code[:index].encode("utf-16-le")) // 2
    return start, start + len(text.encode("utf-16-le")) // 2


def test_instrument_wraps_the_selected_expression_without_moving_its_line():
    code = "def program():\n    return a + b\n"

    instrumented, watches = runner.instrument(code, [_span(code, "a + b")])

    assert instrumented == "def program():\n    return __watch__[0, (a + b)]\n"
    assert watches == [runner.Watch(*_span(code, "a + b"), "a + b")]


def test_instrument_watches_the_assigned_value_when_the_target_is_selected():
    code = "def program():\n    total = count(1)\n"

    instrumented, watches = runner.instrument(code, [_span(code, "total")])

    assert instrumented == "def program():\n    total = __watch__[0, (count(1))]\n"
    assert watches == [runner.Watch(*_span(code, "count(1)"), "total")]


def test_instrument_watches_the_condition_when_the_if_keyword_is_selected():
    code = "def program(x):\n    if x > 1:\n        return 1\n"

    instrumented, watches = runner.instrument(code, [_span(code, "if")])

    assert "    if __watch__[0, (x > 1)]:\n" in instrumented
    assert watches[0].label == "x > 1"


def test_instrument_watches_the_value_of_a_line_selected_with_its_indentation():
    code = "def program():\n    total = count(1)\n    return total\n"
    start, _ = _span(code, "    total")
    _, end = _span(code, "count(1)\n")

    _, watches = runner.instrument(code, [(start, end)])

    assert watches == [runner.Watch(*_span(code, "count(1)"), "total")]


def test_instrument_counts_offsets_in_utf16_like_the_editor():
    code = "def program():\n    # più 🙂\n    return a + b\n"

    instrumented, watches = runner.instrument(code, [_span(code, "b")])

    assert "return a + __watch__[0, (b)]" in instrumented
    assert watches == [runner.Watch(*_span(code, "b"), "b")]


def test_instrument_nests_a_watch_inside_another():
    code = "def program():\n    return a + b\n"

    instrumented, _ = runner.instrument(code, [_span(code, "a + b"), _span(code, "b")])

    assert "return __watch__[0, (a + __watch__[1, (b)])]" in instrumented


def test_instrument_names_a_watch_after_all_the_targets_of_its_assignment():
    code = "def program():\n    source, target = sense(1), sense(2)\n"

    _, watches = runner.instrument(code, [_span(code, "target")])

    assert watches == [runner.Watch(*_span(code, "sense(1), sense(2)"), "source, target")]


def test_instrument_watches_a_walrus_when_its_name_is_selected():
    code = "def program():\n    return (n := count()) + 1\n"

    instrumented, watches = runner.instrument(code, [_span(code, "n", 1)])

    assert "return (__watch__[0, (n := count())]) + 1" in instrumented
    assert watches[0].label == "n"


def test_instrument_watches_the_whole_f_string_when_its_text_is_selected():
    code = 'def program(x):\n    return f"at {x:.1f} km"\n'

    instrumented, _ = runner.instrument(code, [_span(code, "km")])

    assert 'return __watch__[0, (f"at {x:.1f} km")]' in instrumented


@pytest.mark.parametrize("code, selected", [
    ("LIMIT = 3\n\ndef program():\n    return LIMIT\n", "3"),
    ("@aggregate\ndef program():\n    return 1\n", "aggregate"),
    ("def program(x=1):\n    return x\n", "1"),
    ("def program():\n    for i in range(3):\n        pass\n", "i"),
    ("def program(xs):\n    return max(*xs)\n", "*xs"),
    ("def program():\n    a = 1\n    b = 2\n", "a = 1\n    b = 2"),
])
def test_instrument_rejects_a_selection_that_is_not_an_expression_of_a_function(code, selected):
    with pytest.raises(ValueError):
        runner.instrument(code, [_span(code, selected)])


# ---------- running the program on the network of the page ----------

LINE = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]  # three devices in a row, one apart

TIMES_TEN = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id

@aggregate
def helper():
    return -1

@aggregate
def program():
    return local_id() * 10
"""

COUNTER = """
from phyelds.calculus import aggregate, remember

@aggregate
def rounds():
    set_count, count = remember(0)
    return set_count(count + 1)
"""

NEIGHBOURS = """
from phyelds.calculus import aggregate, neighbors

@aggregate
def neighbour_count():
    return len(neighbors(1).exclude_self())
"""

SOURCE = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense

@aggregate
def is_source():
    return sense("source")
"""


def _deployed(tmp_path, code, positions=LINE, radius=1.5, sensors=None, selections=()):
    """A playground running ``code`` on ``positions``, before its first round."""
    playground = runner.Playground(tmp_path / "run")
    playground.update(positions, radius, sensors or {})
    loaded = playground.load(code, list(selections), restart=True)
    assert loaded.ok
    return playground


def _results(snapshot):
    return snapshot.layers[0].numbers


def test_playground_runs_the_last_aggregate_function_on_every_device(tmp_path):
    playground = runner.Playground(tmp_path / "run")
    playground.update(LINE, 1.5, {})

    loaded = playground.load(TIMES_TEN, [], restart=True)
    snapshot = playground.advance(1.0)

    assert loaded.ok
    assert loaded.program == "program"
    assert _results(snapshot) == [0.0, 10.0, 20.0]


def test_playground_runs_every_device_once_per_round(tmp_path):
    positions = [(x / 10, 0.0) for x in range(50)]
    playground = _deployed(tmp_path, COUNTER, positions)

    first = playground.advance(1.0)
    for _ in range(4):
        snapshot = playground.advance(0.5)

    assert _results(first) == [1.0] * 50
    assert _results(snapshot) == [3.0] * 50
    assert snapshot.time == 3.0


def test_playground_changes_the_neighbours_when_the_page_changes_the_radius(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS)
    before = playground.advance(2.0)

    playground.update(LINE, 2.5, {})
    after = playground.advance(2.0)

    assert _results(before) == [1.0, 2.0, 1.0]
    assert _results(after) == [2.0, 2.0, 2.0]


def test_playground_gives_the_program_the_sensors_switched_on_by_the_page(tmp_path):
    playground = _deployed(tmp_path, SOURCE, sensors={"source": [1]})

    snapshot = playground.advance(1.0)

    assert _results(snapshot) == [0.0, 1.0, 0.0]
    assert snapshot.layers[0].texts == ["False", "True", "False"]
    assert snapshot.layers[0].boolean


def test_playground_runs_added_devices_from_the_next_round_and_forgets_removed_ones(tmp_path):
    playground = _deployed(tmp_path, COUNTER, LINE[:2])
    playground.advance(2.0)

    playground.update(LINE, 1.5, {})
    grown = playground.advance(1.0)
    playground.update(LINE[:1], 1.5, {})
    shrunk = playground.advance(0.0)
    # Added back before its next round: the device that was removed must not run again.
    playground.update(LINE[:2], 1.5, {})
    playground.advance(1.0)
    regrown = playground.advance(1.0)

    assert _results(grown) == [3.0, 3.0, 1.0]
    assert _results(shrunk) == [3.0]
    assert _results(regrown) == [5.0, 2.0]


def test_playground_moves_a_device_where_the_page_puts_it(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS)

    playground.update([(0.0, 0.0), (1.0, 0.0), (9.0, 9.0)], 1.5, {})
    snapshot = playground.advance(2.0)

    assert _results(snapshot) == [1.0, 1.0, 0.0]


PRINT_ID = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id

@aggregate
def program():
    print(local_id())
    return local_id()
"""


def test_playground_does_not_run_a_removed_device_again_when_its_id_comes_back(tmp_path, capsys):
    playground = _deployed(tmp_path, PRINT_ID)
    playground.advance(2.0)
    capsys.readouterr()

    playground.update(LINE[:1], 1.5, {})
    playground.update(LINE[:2], 1.5, {})
    playground.advance(2.0)

    runs = capsys.readouterr().out.split()
    assert sorted(runs) == ["0", "0", "1", "1"]


WATCHED = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id

@aggregate
def program():
    if local_id() == 0:
        return local_id() + 10
    double = local_id() * 2
    return double
"""

CONDITIONAL = """
from phyelds.calculus import aggregate, remember
from phyelds.libraries.device import local_id

@aggregate
def program():
    step = 1 if local_id() == 0 else 2
    set_total, total = remember(0)
    return set_total(total + step)
"""

TEXTS = """
from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.device import local_id

@aggregate
def program():
    if local_id() == 0:
        return float("inf")
    if local_id() == 1:
        return None
    return neighbors(local_id())
"""


def test_playground_records_a_watched_expression_on_every_device(tmp_path, capsys):
    playground = _deployed(tmp_path, WATCHED, selections=[_span(WATCHED, "local_id() * 2")])

    snapshot = playground.advance(1.0)

    assert snapshot.layers[1].numbers[1:] == [2.0, 4.0]
    assert snapshot.layers[1].texts[1:] == ["2", "4"]
    assert "AST transformation failed" not in capsys.readouterr().out


def test_playground_leaves_no_value_where_a_device_does_not_reach_the_watched_line(tmp_path):
    playground = _deployed(tmp_path, WATCHED, selections=[_span(WATCHED, "local_id() * 2")])

    snapshot = playground.advance(1.0)

    assert math.isnan(snapshot.layers[1].numbers[0])
    assert snapshot.layers[1].texts[0] == ""


def test_playground_shows_values_without_a_scale_as_text_only(tmp_path):
    playground = _deployed(tmp_path, TEXTS)

    snapshot = playground.advance(1.0)

    assert all(math.isnan(number) for number in _results(snapshot))
    assert snapshot.layers[0].texts[:2] == ["inf", "None"]
    assert snapshot.layers[0].texts[2].startswith("field {")


def test_playground_keeps_the_state_of_the_devices_when_the_watches_change(tmp_path):
    playground = _deployed(tmp_path, COUNTER)
    playground.advance(3.0)

    loaded = playground.load(COUNTER, [_span(COUNTER, "count + 1")], restart=False)
    snapshot = playground.advance(1.0)

    assert loaded.ok
    assert _results(snapshot) == [4.0, 4.0, 4.0]
    assert snapshot.layers[1].numbers == [4.0, 4.0, 4.0]


def test_playground_keeps_the_state_when_a_branch_of_a_conditional_expression_is_watched(tmp_path):
    playground = _deployed(tmp_path, CONDITIONAL)
    playground.advance(3.0)
    branch, _ = _span(CONDITIONAL, "1 if")

    playground.load(CONDITIONAL, [(branch, branch + 1)], restart=False)
    snapshot = playground.advance(1.0)

    assert _results(snapshot) == [4.0, 8.0, 8.0]


def test_playground_forgets_the_values_of_the_old_watches_when_the_watches_change(tmp_path):
    playground = _deployed(tmp_path, WATCHED, selections=[_span(WATCHED, "local_id() * 2")])
    playground.advance(1.0)

    playground.load(WATCHED, [_span(WATCHED, "local_id() + 10")], restart=False)
    snapshot = playground.advance(0.0)

    assert snapshot.layers[1].texts == ["", "", ""]
    assert _results(snapshot) == [10.0, 2.0, 4.0]


def test_playground_starts_every_device_over_on_restart(tmp_path):
    playground = _deployed(tmp_path, COUNTER)
    playground.advance(3.0)

    playground.load(COUNTER, [], restart=True)
    snapshot = playground.advance(1.0)

    assert _results(snapshot) == [1.0, 1.0, 1.0]


LATE_HELPER = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense

@aggregate
def helper():
    return 1

@aggregate
def program():
    return helper() if sense("time") > 2 else 0
"""

FAILING = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id

@aggregate
def program():
    return 1 / local_id()
"""


def test_playground_reports_a_syntax_error_at_its_line_and_keeps_the_running_program(tmp_path, capsys):
    playground = _deployed(tmp_path, TIMES_TEN)
    playground.advance(1.0)

    loaded = playground.load("def broken(:\n", [], restart=True)
    snapshot = playground.advance(1.0)

    assert not loaded.ok
    error = capsys.readouterr().err
    assert 'main.py", line 1' in error
    assert "SyntaxError" in error
    assert _results(snapshot) == [0.0, 10.0, 20.0]


def test_playground_keeps_the_code_of_the_running_program_when_a_load_fails(tmp_path):
    playground = _deployed(tmp_path, LATE_HELPER)
    playground.advance(1.0)

    broken = LATE_HELPER.replace("return 1", "return 99") + "undefined_name\n"
    loaded = playground.load(broken, [], restart=False)
    snapshot = playground.advance(3.0)

    assert not loaded.ok
    assert _results(snapshot) == [1.0, 1.0, 1.0]


@pytest.mark.parametrize("code, selections, message", [
    ("LIMIT = 1\n", [], "Define an @aggregate function"),
    ("from phyelds.calculus import aggregate\n\n@aggregate\ndef program(width):\n    return width\n", [], "width"),
    (TIMES_TEN, [_span(TIMES_TEN, "def helper")], "Select an expression"),
    ("x = 1\nx / 0\n", [], 'main.py", line 2'),
])
def test_playground_explains_why_it_cannot_load_some_code(tmp_path, capsys, code, selections, message):
    playground = runner.Playground(tmp_path / "run")
    playground.update(LINE, 1.5, {})

    loaded = playground.load(code, selections, restart=True)

    assert not loaded.ok
    assert message in capsys.readouterr().err


def test_playground_pauses_on_an_error_in_a_round_and_reports_its_line_once(tmp_path, capsys):
    playground = _deployed(tmp_path, FAILING)

    paused = playground.advance(1.0)
    still = playground.advance(1.0)

    error = capsys.readouterr().err
    assert paused.paused
    assert still.time == paused.time
    assert error.count("ZeroDivisionError") == 1
    assert 'main.py", line 7, in program' in error


def test_playground_resumes_when_the_error_is_fixed(tmp_path):
    playground = _deployed(tmp_path, FAILING)
    playground.advance(1.0)

    loaded = playground.load(FAILING.replace("1 / local_id()", "local_id()"), [], restart=False)
    snapshot = playground.advance(1.0)

    assert loaded.ok
    assert not snapshot.paused
    assert _results(snapshot) == [0.0, 1.0, 2.0]


def test_playground_tells_the_network_is_stable_once_a_whole_round_changes_nothing(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS)

    settling = playground.advance(2.0)
    settled = playground.advance(1.0)

    assert not settling.stable
    assert settled.stable


def test_playground_never_tells_a_network_that_keeps_changing_is_stable(tmp_path):
    playground = _deployed(tmp_path, COUNTER)

    snapshot = playground.advance(5.0)

    assert not snapshot.stable


# ---------- completing names ----------

def _names(suggestions):
    return [suggestion.name for suggestion in suggestions]


def test_complete_suggests_the_modules_of_phyelds_in_an_import():
    code = "from phyelds.libraries import spr"

    suggestions = runner.complete(code, len(code))

    assert runner.Suggestion("spreading", "module") in suggestions


def test_complete_suggests_the_names_of_the_program():
    code = "def program():\n    distance = 1\n    return dis"

    suggestions = runner.complete(code, len(code))

    assert "distance" in _names(suggestions)


def test_complete_counts_offsets_in_utf16_like_the_editor():
    code = "def program():\n    # più 🙂\n    value = 1\n    return val"

    suggestions = runner.complete(code, _span(code, "val", 1)[1])

    assert "value" in _names(suggestions)


def test_complete_works_in_code_that_does_not_compile_yet():
    code = "def program(:\n    distance = 1\n    return dis"

    suggestions = runner.complete(code, len(code))

    assert "distance" in _names(suggestions)


def test_complete_suggests_at_most_a_screenful_of_names():
    code = "import math\nmath."

    suggestions = runner.complete(code, len(code))

    assert 0 < len(suggestions) <= runner.MAX_SUGGESTIONS


# ---------- devices that move ----------

EAST = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense, velocity

@aggregate
def program():
    if not sense("still"):
        velocity.send((10.0, 0.0))
    return local_id()
"""


def _xs(snapshot):
    return [x for x, _ in snapshot.positions]


def test_playground_reports_where_the_devices_are(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS)

    snapshot = playground.advance(1.0)

    assert snapshot.positions == [list(position) for position in LINE]


def test_playground_moves_a_device_by_the_velocity_its_program_sends_up_to_a_top_speed(tmp_path):
    playground = _deployed(tmp_path, EAST, sensors={"still": [1, 2]})
    before = _xs(playground.advance(2.0))

    after = _xs(playground.advance(1.0))

    assert after[0] - before[0] == pytest.approx(runner.MAX_SPEED, abs=0.01)
    assert after[1:] == [1.0, 2.0]


def test_playground_moves_a_device_between_its_rounds_not_in_jumps(tmp_path):
    playground = _deployed(tmp_path, EAST, sensors={"still": [1, 2]})
    xs = [_xs(playground.advance(1.0))[0]]

    for _ in range(4):
        xs.append(_xs(playground.advance(0.25))[0])

    steps = [after - before for before, after in zip(xs, xs[1:])]
    assert steps == pytest.approx([runner.MAX_SPEED / 4] * 4, abs=0.01)


def test_playground_keeps_the_devices_that_move_in_a_world_wider_than_the_arena(tmp_path):
    playground = _deployed(tmp_path, EAST)

    snapshot = playground.advance(100.0)

    assert runner.WORLD == (-2.5, 7.5)
    assert _xs(snapshot) == pytest.approx([7.5] * 3)


def test_playground_keeps_where_the_devices_moved_when_the_page_changes_something_else(tmp_path):
    playground = _deployed(tmp_path, EAST, sensors={"still": [1, 2]})
    moved = _xs(playground.advance(2.0))[0]

    playground.update(LINE, 1.5, {"still": [1, 2]})
    snapshot = playground.advance(0.0)

    assert moved > 0.0
    assert _xs(snapshot)[0] == moved


def test_playground_puts_a_moving_device_where_the_page_drags_it(tmp_path):
    playground = _deployed(tmp_path, EAST, sensors={"still": [0, 1, 2]})
    playground.advance(1.0)

    playground.update([(0.0, 0.0), (1.0, 0.0), (4.0, 3.0)], 1.5, {"still": [0, 1, 2]})
    snapshot = playground.advance(1.0)

    assert snapshot.positions[2] == [4.0, 3.0]


def test_playground_puts_the_devices_back_where_the_page_placed_them_on_restart(tmp_path):
    playground = _deployed(tmp_path, EAST)
    playground.advance(3.0)

    playground.load(EAST, [], restart=True)
    snapshot = playground.advance(0.0)

    assert snapshot.positions == [list(position) for position in LINE]


def test_playground_never_tells_a_network_whose_devices_move_is_stable(tmp_path):
    playground = _deployed(tmp_path, EAST, positions=[(0.0, 0.0)])

    snapshots = [playground.advance(1.0) for _ in range(5)]

    assert not any(snapshot.stable for snapshot in snapshots)


# ---------- ranges that adapt ----------

CROWD = [(x / 5, y / 5) for y in range(6) for x in range(6)]  # 36 devices in a unit


def test_playground_starts_every_device_with_the_radius_of_the_page(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS)

    snapshot = playground.advance(0.0)

    assert snapshot.ranges == [1.5, 1.5, 1.5]


def test_playground_shrinks_the_range_of_crowded_devices_to_keep_a_few_neighbours(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS, CROWD)

    snapshot = playground.advance(40.0)

    assert all(reach < 1.5 for reach in snapshot.ranges)
    assert max(_results(snapshot)) <= runner.NEIGHBOURS + runner.TOLERANCE


def test_playground_keeps_the_ranges_when_the_page_changes_something_else(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS, CROWD)
    shrunk = playground.advance(20.0).ranges

    playground.update(CROWD, 1.5, {"source": [0]})
    kept = playground.advance(0.0).ranges

    assert kept == shrunk


def test_playground_starts_the_ranges_over_when_the_page_changes_the_radius_or_restarts(tmp_path):
    playground = _deployed(tmp_path, NEIGHBOURS, CROWD)
    playground.advance(20.0)

    playground.update(CROWD, 2.0, {})
    changed = playground.advance(0.0).ranges
    playground.advance(20.0)
    playground.load(NEIGHBOURS, [], restart=True)
    restarted = playground.advance(0.0).ranges

    assert changed == [2.0] * 36
    assert restarted == [2.0] * 36


HEADINGS = """
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector
from phyelds.libraries.device import local_id

@aggregate
def program():
    return [Vector(0.951, 0.234), Vector(0, 1), Vector(0.001, 0, 2)][local_id()]
"""


def test_playground_shows_vectors_as_directions_in_degrees(tmp_path):
    playground = _deployed(tmp_path, HEADINGS)

    layer = playground.advance(1.0).layers[0]

    assert layer.direction
    assert layer.numbers[:2] == [pytest.approx(13.82, abs=0.01), 90.0]
    assert math.isnan(layer.numbers[2])  # all but still on the plane: no heading
    assert layer.texts == ["(x=0.95, y=0.23)", "(x=0.00, y=1.00)", "(x=0.00, y=0.00, z=2.00)"]


PHASES = """
from enum import IntEnum
from phyelds.calculus import aggregate

class Light(IntEnum):
    GREEN = 0
    YELLOW = 1
    RED = 2

@aggregate
def program():
    return Light.YELLOW
"""


def test_playground_scales_an_enum_on_all_its_members_and_names_them(tmp_path):
    playground = _deployed(tmp_path, PHASES)

    layer = playground.advance(1.0).layers[0]

    assert (layer.low, layer.high) == (0.0, 2.0)
    assert layer.numbers == [1.0, 1.0, 1.0]
    assert [key[0] for key in layer.keys] == ["GREEN", "YELLOW", "RED"]
    assert layer.texts == ["YELLOW"] * 3


def test_playground_widens_the_scale_of_a_layer_but_never_narrows_it_in_a_run(tmp_path):
    playground = _deployed(tmp_path, COUNTER)
    first = playground.advance(1.0).layers[0]

    later = playground.advance(3.0).layers[0]
    playground.load(COUNTER, [], restart=True)
    restarted = playground.advance(1.0).layers[0]

    assert (first.low, first.high) == (1.0, 1.0)
    assert (later.low, later.high) == (1.0, 4.0)
    assert (restarted.low, restarted.high) == (1.0, 1.0)


def test_playground_colours_the_members_of_an_enum_named_after_colours(tmp_path):
    playground = _deployed(tmp_path, PHASES)

    layer = playground.advance(1.0).layers[0]

    assert layer.colours == ["yellow"] * 3
    assert layer.keys == [["GREEN", "green", 0.0], ["YELLOW", "yellow", 1.0], ["RED", "red", 2.0]]


def test_playground_colours_nothing_by_name_when_a_value_names_no_colour(tmp_path):
    playground = _deployed(tmp_path, COUNTER)

    layer = playground.advance(1.0).layers[0]

    assert layer.colours == [""] * 3
    assert layer.keys == []


MARKED = """
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id

@aggregate
def program():
    double = local_id() * 2  # watch
    return double + 1
"""


def test_playground_watches_the_lines_marked_watch_when_it_runs_the_code(tmp_path):
    playground = runner.Playground(tmp_path / "run")
    playground.update(LINE, 1.5, {})

    loaded = playground.load(MARKED, [], restart=True)
    snapshot = playground.advance(1.0)

    assert [watch.label for watch in loaded.watches] == ["double"]
    assert snapshot.layers[1].numbers == [0.0, 2.0, 4.0]


def test_playground_watches_a_marked_line_once_when_it_is_also_selected(tmp_path):
    playground = runner.Playground(tmp_path / "run")
    playground.update(LINE, 1.5, {})

    # As the page sends it: a list, not a tuple.
    loaded = playground.load(MARKED, [list(_span(MARKED, "double = local_id() * 2"))], restart=True)

    assert [watch.label for watch in loaded.watches] == ["double"]


def test_playground_leaves_the_marks_alone_when_the_watches_change_on_the_running_devices(tmp_path):
    playground = _deployed(tmp_path, MARKED)

    loaded = playground.load(MARKED, [], restart=False)

    assert loaded.watches == []

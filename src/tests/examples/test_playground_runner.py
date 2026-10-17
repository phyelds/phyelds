"""Keeps the Python side of the browser playground working, outside the browser."""
import importlib.util
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[3] / "docs" / "playground" / "runner.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("playground_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()

SAVE_A_GIF = """
from phyelds.simulator import Simulator
from phyelds.simulator.effects import DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.render import RenderMonitor

simulator = Simulator()
simulator.create_node((0.0, 0.0), node_id=0)
simulator.create_node((1.0, 0.0), node_id=1)
simulator.schedule_event(1.0, lambda: None)
RenderMonitor(simulator, RenderConfig(effects=[DrawNodes()], mode=RenderMode.SAVE, save_as="field.gif"))
simulator.run(2.0)
"""


def test_run_user_code_returns_the_gif_saved_by_the_program(tmp_path):
    result = runner.run_user_code(SAVE_A_GIF, tmp_path / "run")

    assert result.ok
    assert [output.name for output in result.outputs] == ["field.gif"]
    assert result.outputs[0].data.startswith(b"GIF")


def test_run_user_code_returns_the_figures_left_open_by_the_program(tmp_path):
    code = "from matplotlib import pyplot as plt\nplt.plot([0, 1], [1, 0])\n"

    result = runner.run_user_code(code, tmp_path / "run")

    assert [output.name for output in result.outputs] == ["figure-1.png"]
    assert result.outputs[0].data.startswith(b"\x89PNG")


def test_run_user_code_reports_an_error_from_the_line_of_the_program(tmp_path, capsys):
    code = "x = 1\nx / 0\n"

    result = runner.run_user_code(code, tmp_path / "run")

    assert not result.ok
    error = capsys.readouterr().err
    assert 'main.py", line 2' in error
    assert "ZeroDivisionError" in error
    assert "runpy" not in error


def test_run_user_code_reports_a_syntax_error_without_the_runner_frames(tmp_path, capsys):
    result = runner.run_user_code("def broken(:\n", tmp_path / "run")

    assert not result.ok
    error = capsys.readouterr().err
    assert 'main.py", line 1' in error
    assert "SyntaxError" in error
    assert "runpy" not in error


ALIGNED_PROGRAM = """
from phyelds.calculus import aggregate
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all

@aggregate
def program():
    if True:
        return 1
    return 0

simulator = Simulator()
simulator.create_node((0.0, 0.0), node_id=0)
schedule_program_for_all(simulator, 0.0, 1.0, program)
simulator.run(1.0)
"""


def test_run_user_code_lets_aggregate_read_the_source_of_the_program(tmp_path, capsys):
    result = runner.run_user_code(ALIGNED_PROGRAM, tmp_path / "run")

    assert result.ok
    assert "AST transformation failed" not in capsys.readouterr().out


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

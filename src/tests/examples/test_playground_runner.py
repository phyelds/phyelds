"""Keeps the Python side of the browser playground working, outside the browser."""
import importlib.util
from pathlib import Path

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

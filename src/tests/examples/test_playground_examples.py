"""Keeps the examples of the playground running, through the same runner as the browser."""
import importlib.util
from pathlib import Path

import pytest

from phyelds.simulator import runner as simulator_runner

DOCS = Path(__file__).resolve().parents[3] / "docs"
EXAMPLES = DOCS / "examples" / "playground"
NAMES = ["neighbours", "gradient", "self_healing", "channel", "leaders", "bubbles"]
# Pyodide is a few times slower than CPython, so the examples must stay small. The
# size is counted in rounds (one device running the program once), not in seconds,
# so that the check does not depend on the speed of the machine. 4000 rounds take
# about 7 seconds in the browser.
ROUND_BUDGET = 4000


def _load_runner():
    spec = importlib.util.spec_from_file_location("playground_runner", DOCS / "playground" / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


def _count_rounds(monkeypatch) -> list[int]:
    """Count every round run by aggregate_program_runner from now on."""
    rounds = [0]
    run_round = simulator_runner.aggregate_program_runner

    def counting_runner(*args, **kwargs):
        rounds[0] += 1
        return run_round(*args, **kwargs)

    monkeypatch.setattr(simulator_runner, "aggregate_program_runner", counting_runner)
    return rounds


@pytest.mark.parametrize("name", NAMES)
def test_playground_example_saves_an_animation_with_a_small_simulation(name, tmp_path, monkeypatch):
    code = (EXAMPLES / f"{name}.py").read_text()
    rounds = _count_rounds(monkeypatch)

    result = runner.run_user_code(code, tmp_path / "run")

    assert result.ok
    assert f"{name}.gif" in [output.name for output in result.outputs]
    assert 0 < rounds[0] <= ROUND_BUDGET

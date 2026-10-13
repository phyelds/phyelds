"""Keeps the examples of the playground running, through the same runner as the browser."""
import importlib.util
import time
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs"
EXAMPLES = DOCS / "examples" / "playground"
NAMES = ["neighbours", "gradient", "self_healing", "channel"]
# Pyodide is a few times slower than CPython: keep every example quick to run here.
TIME_BUDGET_SECONDS = 5.0


def _load_runner():
    spec = importlib.util.spec_from_file_location("playground_runner", DOCS / "playground" / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


@pytest.mark.parametrize("name", NAMES)
def test_playground_example_saves_an_animation_quickly(name, tmp_path):
    code = (EXAMPLES / f"{name}.py").read_text()

    start = time.perf_counter()
    result = runner.run_user_code(code, tmp_path / "run")
    elapsed = time.perf_counter() - start

    assert result.ok
    assert f"{name}.gif" in [output.name for output in result.outputs]
    assert elapsed < TIME_BUDGET_SECONDS

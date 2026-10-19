"""
What runs on MicroPython: the programs of programs.py, on the unix port of MicroPython.

Skipped when ``micropython`` is not on the PATH; the CI builds it.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from phyelds.data import NeighborhoodField
from phyelds.data.codec import decode, encode
from phyelds.micropython.build import build
from tests.micropython import programs

MICROPYTHON = shutil.which("micropython")
# Enough for all the libraries and four devices in one process. Objects take about twice
# the memory on the 64-bit unix port than on an ESP32.
HEAP = "512k"

pytestmark = pytest.mark.skipif(MICROPYTHON is None, reason="micropython is not on the PATH")


@pytest.fixture(scope="module", name="bundle")
def fixture_bundle(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("bundle")
    build([Path(programs.__file__)], out_dir)
    return out_dir


def _on_micropython(bundle: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [MICROPYTHON, "-X", f"heapsize={HEAP}", "programs.py", *arguments],
        cwd=bundle, capture_output=True, text=True, check=False,
    )


def _comparable(value):
    """``value`` with its fields, which have no ``==``, as tuples."""
    if isinstance(value, NeighborhoodField):
        return ("field", value.node_id, _comparable(value.data), _comparable(value.default))
    if isinstance(value, dict):
        return {key: _comparable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_comparable(item) for item in value)
    return value


def _micropython(bundle: Path, *arguments: str):
    completed = _on_micropython(bundle, *arguments)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    return _comparable(decode(completed.stdout.encode()))


def _cpython(program: str, paths: str = "debug"):
    return _comparable(decode(encode(programs.run(getattr(programs, program), paths))))


@pytest.mark.parametrize("program", [
    "neighbour_ids",
    "remembered",
    "exchanged",
    "branches",
    "conditional_expression",
    "state_arithmetic",
    "field_operations",
    "gradient",
    "broadcasted",
    "cast_with_a_three_argument_function",
    "collected",
    "gossiped",
    "leader",
    "timed",
    "spatial_logic",
    "processes",
    "state_machine",
])
def test_micropython_runs_programs_like_cpython(bundle, program):
    assert _micropython(bundle, program) == _cpython(program)


def test_micropython_and_cpython_send_the_same_compact_messages(bundle):
    results, outboxes = _micropython(bundle, "gossiped", "compact")

    assert (results, outboxes) == _cpython("gossiped", "compact")
    assert all(isinstance(key, int) for outbox in outboxes.values() for key in outbox)


def test_micropython_cannot_tell_the_parameters_of_a_lambda(bundle):
    # Accumulations given as lambdas are called with the data only: a lambda with more
    # parameters must be a function defined at the top of the program.
    completed = _on_micropython(bundle, "cast_with_a_two_argument_lambda")

    assert completed.returncode != 0
    assert "TypeError" in completed.stdout + completed.stderr


def test_micropython_does_not_reflect_comparisons_onto_states(bundle):
    # 2 < state fails: MicroPython does not try state > 2. Write state > 2 instead.
    completed = _on_micropython(bundle, "value_compared_to_state")

    assert completed.returncode != 0
    assert "unsupported types for __lt__: 'int', 'State'" in completed.stdout


def test_micropython_states_are_not_instances_of_their_value_type(bundle):
    results, _ = _micropython(bundle, "state_type")

    assert set(results.values()) == {False}
    assert set(_cpython("state_type")[0].values()) == {True}

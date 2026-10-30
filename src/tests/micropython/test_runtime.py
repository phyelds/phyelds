"""
What runs on MicroPython: the programs of programs.py, on the unix port of MicroPython, and
how much heap minimal.py needs; built as ``.py`` and, with ``mpy-cross``, as ``.mpy``.

Skipped when ``micropython`` (or ``mpy-cross``) is not on the PATH; the CI builds them.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from phyelds.data import NeighborhoodField
from phyelds.data.codec import decode, encode
from phyelds.micropython.build import build
from tests.micropython import minimal, programs

MICROPYTHON = shutil.which("micropython")
# Enough for all the libraries and four devices in one process. Objects take about twice
# the memory on the 64-bit unix port than on an ESP32.
HEAP = "512k"
# The heap minimal.py needs, with a margin: the need is not monotonic, as the heap fragments.
# Lower them when a change saves memory, so that regressions show up.
MINIMAL_BUDGET = {"py": "90k", "mpy": "64k", "pruned": "60k"}

pytestmark = pytest.mark.skipif(MICROPYTHON is None, reason="micropython is not on the PATH")
needs_mpy_cross = pytest.mark.skipif(shutil.which("mpy-cross") is None, reason="mpy-cross is not on the PATH")
# As .py, as .mpy, and as .mpy without the definitions the program never names.
BUNDLES = ["py", pytest.param("mpy", marks=needs_mpy_cross), pytest.param("pruned", marks=needs_mpy_cross)]


@pytest.fixture(scope="module", name="bundle", params=BUNDLES)
def fixture_bundle(request, tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("bundle")
    build([Path(programs.__file__)], out_dir, **_options(request.param))
    return out_dir


def _options(kind: str) -> dict:
    return {"mpy": kind != "py", "prune": kind == "pruned"}


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


PROGRAMS = [
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
    "described_state_machine",
    "swarm_blocks",
    "formed",
]


@pytest.mark.parametrize("program", PROGRAMS)
def test_micropython_runs_programs_like_cpython(bundle, program):
    assert _micropython(bundle, program) == _cpython(program)


@pytest.mark.parametrize(
    ("program", "paths"), [(program, "compact") for program in PROGRAMS] + [("gossiped", "debug")]
)
def test_micropython_round_trips_the_messages_of_programs_in_the_binary_format(bundle, program, paths):
    assert _micropython(bundle, program, paths, "binary") == _cpython(program, paths)


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


@pytest.mark.parametrize("kind", BUNDLES)
def test_micropython_runs_a_minimal_program_within_its_heap_budget(tmp_path, kind):
    build([Path(minimal.__file__)], tmp_path, **_options(kind))

    completed = subprocess.run(
        [MICROPYTHON, "-X", f"heapsize={MINIMAL_BUDGET[kind]}", "minimal.py"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert completed.stdout.strip() == str(minimal.run())

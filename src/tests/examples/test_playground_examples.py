"""Keeps the examples of the playground running, through the same runner as the browser."""
import importlib.util
import math
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs"
EXAMPLES = DOCS / "examples" / "playground"
NAMES = sorted(path.stem for path in EXAMPLES.glob("*.py"))
# A 6x6 grid one apart, in the arena of the page, and the sensors the examples read.
GRID = [(float(x), float(y)) for y in range(6) for x in range(6)]
SENSORS = {"source": [0], "target": [35], "alarm": [14], "high": [14], "vote": [0], "zone": [14]}


def _load_runner():
    spec = importlib.util.spec_from_file_location("playground_runner", DOCS / "playground" / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


@pytest.mark.parametrize("name", NAMES)
def test_playground_example_gives_every_device_a_value_on_a_small_network(name, tmp_path):
    playground = runner.Playground(tmp_path / "run")
    playground.update(GRID, 1.5, SENSORS)

    loaded = playground.load((EXAMPLES / f"{name}.py").read_text(), [], restart=True)
    snapshot = playground.advance(15.0)

    assert loaded.ok
    assert not snapshot.paused
    assert all(math.isfinite(number) for number in snapshot.layers[0].numbers)


def test_playground_channel_example_keeps_the_devices_along_the_shortest_path(tmp_path):
    playground = runner.Playground(tmp_path / "run")
    playground.update(GRID, 1.5, SENSORS)
    playground.load((EXAMPLES / "channel.py").read_text(), [], restart=True)

    in_channel = playground.advance(15.0).layers[0].numbers

    assert [in_channel[device] for device in (0, 7, 14, 21, 28, 35)] == [1.0] * 6
    assert in_channel[5] == in_channel[30] == 0.0


def _running(name, sensors, tmp_path, rounds=15.0):
    playground = runner.Playground(tmp_path / "run")
    playground.update(GRID, 1.5, sensors)
    playground.load((EXAMPLES / f"{name}.py").read_text(), [], restart=True)
    return playground, playground.advance(rounds).layers[0].numbers


def test_playground_census_example_tells_every_device_the_size_of_the_network(tmp_path):
    _, sizes = _running("census", {"source": [0]}, tmp_path)

    assert sizes == [36.0] * 36


def test_playground_gossip_example_forgets_a_maximum_once_it_is_gone(tmp_path):
    playground, before = _running("gossip", {"high": [14]}, tmp_path)

    playground.update(GRID, 1.5, {"high": []})
    after = playground.advance(15.0).layers[0].numbers

    assert before == [100.0] * 36
    assert after == [35.0] * 36


def test_playground_trail_example_remembers_where_the_source_was(tmp_path):
    playground, _ = _running("trail", {"source": [0]}, tmp_path)

    playground.update(GRID, 1.5, {"source": [35]})
    lit = playground.advance(15.0).layers[0].numbers

    assert lit[0] == lit[35] == 1.0
    assert lit[17] == 0.0


def test_playground_regions_example_finds_the_boundary_of_a_block(tmp_path):
    block = [7, 8, 9, 13, 14, 15, 19, 20, 21]

    _, border = _running("regions", {"zone": block}, tmp_path)

    assert border[14] == 0.0
    assert border[7] == border[0] == 1.0
    assert border[35] == 0.0


def test_playground_lights_example_goes_through_its_phases_together(tmp_path):
    playground, _ = _running("lights", {}, tmp_path, rounds=0.5)
    seen = []
    for _ in range(30):
        phases = set(playground.advance(1.0).layers[0].numbers)
        if len(phases) == 1:
            seen.append(phases.pop())

    assert {0.0, 1.0, 2.0} <= set(seen)

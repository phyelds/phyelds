"""Keeps the examples of the playground running, through the same runner as the browser."""
import importlib.util
import math
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[3] / "docs"
EXAMPLES = DOCS / "examples" / "playground"
NAMES = ["neighbours", "gradient", "self_healing", "channel", "corridor", "leaders", "bubbles"]
# A 6x6 grid one apart, in the arena of the page, and the sensors the examples read.
GRID = [(float(x), float(y)) for y in range(6) for x in range(6)]
SENSORS = {"source": [0], "target": [35], "alarm": [14]}


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

"""Runs the Webots example of the docs in Webots itself, headless."""
import shutil

import pytest
from session import ROOT, WEBOTS, run_world

EXAMPLE = ROOT / "docs" / "examples" / "webots"
EXPECTED = {"source": "0.00m", "robot1": "0.10m", "robot2": "0.20m", "robot3": "0.30m", "robot4": "0.40m"}


@pytest.mark.skipif(WEBOTS is None, reason="webots is not on the PATH")
def test_webots_example_measures_the_distance_from_the_source_without_gps(tmp_path):
    # The documented world, with each robot logging its label at every round.
    world = shutil.copytree(EXAMPLE, tmp_path / "webots") / "worlds" / "line.wbt"
    world.write_text(world.read_text().replace('"--source"', '"--trace" "--source"'))

    labels, output = run_world(world, done=lambda labels: labels == EXPECTED)

    assert labels == EXPECTED, output

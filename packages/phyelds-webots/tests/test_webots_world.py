"""Runs the Webots example of the docs in Webots itself, headless."""
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "docs" / "examples" / "webots"
WEBOTS = shutil.which("webots")
EXPECTED = {"source": "0.00m", "robot1": "0.10m", "robot2": "0.20m", "robot3": "0.30m", "robot4": "0.40m"}
TIMEOUT = 120


@pytest.mark.skipif(WEBOTS is None, reason="webots is not on the PATH")
def test_webots_example_measures_the_distance_from_the_source_without_gps(tmp_path):
    # The documented world, with each robot logging its label at every round.
    world = shutil.copytree(EXAMPLE, tmp_path / "webots") / "worlds" / "line.wbt"
    world.write_text(world.read_text().replace('"--source"', '"--trace" "--source"'))
    # The controllers run on the python3 of this environment, with phyelds from the sources.
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "packages" / "phyelds-webots" / "src")]),
    }
    webots = subprocess.Popen(  # pylint: disable=consider-using-with
        [WEBOTS, "--batch", "--mode=fast", "--no-rendering", "--minimize", "--stdout", "--stderr", str(world)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
        start_new_session=True,  # webots is a launcher: webots-bin and the controllers are its children
    )
    timer = threading.Timer(TIMEOUT, os.killpg, (webots.pid, signal.SIGKILL))
    timer.start()
    labels, output = {}, []
    try:
        for line in webots.stdout:
            output.append(line)
            name, _, label = line.strip().partition(" round: ")
            if label:
                labels[name] = label
            if labels == EXPECTED:
                break
    finally:
        timer.cancel()
        os.killpg(webots.pid, signal.SIGKILL)
        webots.wait()

    assert labels == EXPECTED, "".join(output[-50:])

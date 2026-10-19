"""Runs the Webots example of the docs in Webots itself, headless."""
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WORLD = ROOT / "docs" / "examples" / "webots" / "worlds" / "line.wbt"
WEBOTS = shutil.which("webots")
EXPECTED = {"source": 0, "robot1": 1, "robot2": 2, "robot3": 3, "robot4": 4}
TIMEOUT = 120


@pytest.mark.skipif(WEBOTS is None, reason="webots is not on the PATH")
def test_webots_example_computes_the_hops_from_the_source():
    # The controllers run on the python3 of this environment, with phyelds from the sources.
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "packages" / "phyelds-webots" / "src")]),
    }
    webots = subprocess.Popen(  # pylint: disable=consider-using-with
        [WEBOTS, "--batch", "--mode=fast", "--no-rendering", "--minimize", "--stdout", "--stderr", str(WORLD)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
    )
    timer = threading.Timer(TIMEOUT, webots.kill)
    timer.start()
    hops, output = {}, []
    try:
        for line in webots.stdout:
            output.append(line)
            if line.startswith("phyelds "):
                _, name, value = line.split()
                hops[name] = float(value)
            if hops == EXPECTED:
                break
    finally:
        timer.cancel()
        webots.kill()
        webots.wait()

    assert hops == EXPECTED, "".join(output[-50:])

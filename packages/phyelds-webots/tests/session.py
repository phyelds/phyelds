"""Runs a world in Webots, headless, and reads the labels its robots log with ``--trace``."""
import os
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEBOTS = shutil.which("webots")


def run_world(world: Path, done: Callable[[dict[str, str]], bool], timeout: float = 120) -> tuple[dict[str, str], str]:
    """
    Run ``world`` until ``done`` holds of the last label of each robot, or ``timeout`` seconds pass.

    Returns:
        The last label of each robot, by name, and the end of the output, to explain a failure.
    """
    # The controllers run on the python3 of this environment, with phyelds from the sources and
    # the programs of the tests.
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "PYTHONPATH": os.pathsep.join(
            str(path) for path in (ROOT / "src", ROOT / "packages" / "phyelds-webots" / "src", Path(__file__).parent)
        ),
    }
    webots = subprocess.Popen(  # pylint: disable=consider-using-with
        [WEBOTS, "--batch", "--mode=fast", "--no-rendering", "--minimize", "--stdout", "--stderr", str(world)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
        start_new_session=True,  # webots is a launcher: webots-bin and the controllers are its children
    )
    timer = threading.Timer(timeout, os.killpg, (webots.pid, signal.SIGKILL))
    timer.start()
    labels, output = {}, []
    try:
        for line in webots.stdout:
            output.append(line)
            name, _, label = line.strip().partition(" round: ")
            if label:
                labels[name] = label
            if done(labels):
                break
    finally:
        timer.cancel()
        os.killpg(webots.pid, signal.SIGKILL)
        webots.wait()
    return labels, "".join(output[-50:])

"""
Run a program written in the playground and collect what it produced.

The playground loads this module into Pyodide; it is plain Python, so it is
tested with pytest like the rest of the documentation examples.
"""
import contextlib
import io
import runpy
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from matplotlib import pyplot as plt

PRODUCED_SUFFIXES = (".gif", ".png")


@dataclass
class Output:
    """A file produced by the program."""

    name: str
    data: bytes


@dataclass
class RunResult:
    """Whether the program ended without errors, and what it produced."""

    ok: bool
    outputs: list[Output] = field(default_factory=list)


def run_user_code(code: str, run_dir: Path) -> RunResult:
    """
    Run ``code`` as ``__main__`` from a file in the empty directory ``run_dir``.

    Args:
        code: the program.
        run_dir: where the program runs; it is emptied first.

    Returns:
        The outcome of the run, the images the program saved and the figures it
        left open.
    """
    plt.close("all")
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    main = run_dir / "main.py"
    main.write_text(code)
    ok = True
    with contextlib.chdir(run_dir):
        try:
            runpy.run_path(str(main), run_name="__main__")
        # Any error of the program is reported to its author, like Python would.
        except Exception as error:  # pylint: disable=broad-exception-caught
            ok = False
            _print_traceback(error, main)
    return RunResult(ok=ok, outputs=_produced_files(run_dir) + _open_figures())


def _print_traceback(error: Exception, main: Path) -> None:
    """
    Print the traceback of ``error`` to stderr, from the first frame of ``main`` on.
    A program that does not compile has no such frame: only the error is printed.
    """
    frames = traceback.extract_tb(error.__traceback__)
    first = next((index for index, frame in enumerate(frames) if frame.filename == str(main)), None)
    lines = []
    if first is not None:
        lines += ["Traceback (most recent call last):\n"]
        lines += traceback.format_list(frames[first:])
    lines += traceback.format_exception_only(error)
    print("".join(lines), end="", file=sys.stderr)


def _produced_files(run_dir: Path) -> list[Output]:
    """The images in ``run_dir``, without the PNG that RenderMonitor saves next to each GIF."""
    paths = sorted(path for path in run_dir.iterdir() if path.suffix in PRODUCED_SUFFIXES)
    gifs = {path.stem for path in paths if path.suffix == ".gif"}
    return [
        Output(path.name, path.read_bytes())
        for path in paths
        if not (path.suffix == ".png" and path.stem in gifs)
    ]


def _open_figures() -> list[Output]:
    """The figures still open, as PNG images; they are closed afterwards."""
    outputs = []
    for number in plt.get_fignums():
        buffer = io.BytesIO()
        plt.figure(number).savefig(buffer, format="png")
        outputs.append(Output(f"figure-{number}.png", buffer.getvalue()))
    plt.close("all")
    return outputs

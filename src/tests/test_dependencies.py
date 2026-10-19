"""The core stays minimal: the simulator and its dependencies live in phyelds-simulator."""
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_core_depends_only_on_wrapt():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert set(project["tool"]["poetry"]["dependencies"]) == {"python", "wrapt"}
    assert "extras" not in project["tool"]["poetry"]


def test_core_does_not_ship_the_simulator():
    assert not (ROOT / "src" / "phyelds" / "simulator").exists()


def test_core_import_does_not_load_the_simulator_dependencies():
    core = ", ".join(
        f"phyelds.libraries.{path.stem}"
        for path in (ROOT / "src" / "phyelds" / "libraries").glob("[!_]*.py")
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys, phyelds.calculus, phyelds.data.codec, phyelds.vm.internal, {core}; "
            "heavy = {'matplotlib', 'pandas', 'pydantic', 'phyelds.simulator'}; "
            "assert not heavy & set(sys.modules), heavy & set(sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

"""The core stays minimal: the simulator and its dependencies live in phyelds-simulator."""
import os
import subprocess
import sys
import sysconfig
import tomllib
from pathlib import Path

import pytest

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


def _core_modules():
    source = ROOT / "src"
    return sorted(
        ".".join(path.relative_to(source).with_suffix("").parts).removesuffix(".__init__")
        for package in ("calculus", "data", "libraries", "vm", "experimental")
        for path in (source / "phyelds" / package).rglob("*.py")
        if path.stem != "__main__"
    )


@pytest.mark.skipif(not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded Python")
def test_core_import_keeps_the_gil_disabled_on_a_free_threaded_python():
    environment = {name: value for name, value in os.environ.items() if name != "PYTHON_GIL"}

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys, {', '.join(_core_modules())}; "
            "assert not sys._is_gil_enabled(), 'a module of the core enabled the GIL'",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr

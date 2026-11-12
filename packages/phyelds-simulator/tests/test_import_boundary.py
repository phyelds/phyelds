"""Tests for dependencies intentionally excluded from the core and simulator packages."""

import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tomllib

import pytest

SIMULATOR_ROOT = Path(__file__).resolve().parents[1]


def test_simulator_import_does_not_load_vmas():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import phyelds.simulator; "
            "assert not any(name == 'vmas' or name.startswith('vmas.') "
            "for name in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_render_import_works_without_ipython():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['IPython'] = None; "
            "import phyelds.simulator.render",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_simulator_does_not_depend_on_or_import_pandas():
    project = tomllib.loads((SIMULATOR_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pandas" not in project["tool"]["poetry"]["dependencies"]

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, phyelds.simulator, phyelds.simulator.exporter, "
            "phyelds.simulator.runner, phyelds.simulator.neighborhood; "
            "assert 'pandas' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded Python"
)
def test_simulator_headless_modules_keep_the_gil_disabled():
    environment = {name: value for name, value in os.environ.items() if name != "PYTHON_GIL"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, phyelds.simulator, phyelds.simulator.exporter, "
            "phyelds.simulator.runner, phyelds.simulator.neighborhood, "
            "phyelds.simulator.deployments, phyelds.simulator.actions; "
            "assert not sys._is_gil_enabled(), 'a simulator module enabled the GIL'",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr

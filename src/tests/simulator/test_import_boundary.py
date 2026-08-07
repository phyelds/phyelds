"""Tests for dependencies intentionally excluded from the core package."""

import subprocess
import sys


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
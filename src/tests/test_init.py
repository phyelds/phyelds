"""The phyelds package: a namespace shared with the extension packages."""
import subprocess
import sys
from pathlib import Path

import phyelds


def test_phyelds_namespace_includes_the_simulator_package():
    assert any(Path(path).parts[-3:] == ("phyelds-simulator", "src", "phyelds") for path in phyelds.__path__)


def test_phyelds_imports_without_pkgutil():
    # As on MicroPython, which has no pkgutil: phyelds is then a plain package.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['pkgutil'] = None; import phyelds; print(len(phyelds.__path__))",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1"

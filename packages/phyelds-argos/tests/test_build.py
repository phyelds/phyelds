"""Build the ARGoS plugin from the sources the package ships."""
from pathlib import Path
import shutil
import subprocess

from phyelds.argos import build
from phyelds.argos.build import build_plugin


def test_build_plugin_reconfigures_a_build_directory_made_from_other_sources(tmp_path):
    other_sources = shutil.copytree(Path(build.__file__).parent / "native", tmp_path / "native")
    build_dir = tmp_path / "build"
    subprocess.run(["cmake", "-S", str(other_sources), "-B", str(build_dir), "-DPHYELDS_ARGOS_GUI=OFF"],
                   check=True, capture_output=True)

    library = build_plugin(build_dir, gui=False)

    assert library.is_file()

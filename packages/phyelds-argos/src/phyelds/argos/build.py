"""Build the ARGoS plugin against the Python running this command."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

_SOURCE_ENTRY = "CMAKE_HOME_DIRECTORY:INTERNAL="


def build_plugin(build_dir: Path, *, gui: bool = True) -> Path:
    """Compile the host and return the controller plugin path.

    Args:
        build_dir: Directory for CMake artifacts and the compiled plugins.
        gui: Whether to also build the Qt/OpenGL halo and label renderer.

    Returns:
        The absolute path of the controller library.

    Raises:
        subprocess.CalledProcessError: If configuration or compilation fails.
        FileNotFoundError: If CMake or the built controller cannot be found.
    """
    build_dir = Path(build_dir).absolute()
    source = Path(__file__).parent / "native"
    _forget_other_sources(build_dir, source)
    subprocess.run([
        "cmake", "-S", str(source), "-B", str(build_dir),
        f"-DPython3_EXECUTABLE={sys.executable}", "-DCMAKE_BUILD_TYPE=Release",
        f"-DPHYELDS_ARGOS_GUI={'ON' if gui else 'OFF'}",
    ], check=True)
    subprocess.run(["cmake", "--build", str(build_dir), "--parallel"], check=True)
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    plugin = build_dir / f"libphyelds_argos{suffix}"
    if not plugin.is_file():
        raise FileNotFoundError(plugin)
    return plugin


def _forget_other_sources(build_dir: Path, source: Path) -> None:
    """Drop a CMake cache made from other sources, such as another install, which CMake refuses."""
    cache = build_dir / "CMakeCache.txt"
    if cache.is_file() and _cached_source(cache) != source.resolve():
        cache.unlink()
        shutil.rmtree(build_dir / "CMakeFiles", ignore_errors=True)


def _cached_source(cache: Path) -> Path | None:
    """The source directory a CMake cache was made from, if it records one."""
    for line in cache.read_text().splitlines():
        if line.startswith(_SOURCE_ENTRY):
            return Path(line.removeprefix(_SOURCE_ENTRY)).resolve()
    return None


def main() -> None:
    """Compile the plugins using command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--no-gui", action="store_true", help="do not require Qt/OpenGL")
    args = parser.parse_args()
    print(build_plugin(args.build_dir, gui=not args.no_gui))


if __name__ == "__main__":
    main()

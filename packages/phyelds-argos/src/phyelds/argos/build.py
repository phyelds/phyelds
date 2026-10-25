"""Build the ARGoS plugin against the Python running this command."""
import argparse
from pathlib import Path
import subprocess
import sys


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


def main() -> None:
    """Compile the plugins using command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--no-gui", action="store_true", help="do not require Qt/OpenGL")
    args = parser.parse_args()
    print(build_plugin(args.build_dir, gui=not args.no_gui))


if __name__ == "__main__":
    main()

"""Compile and load the C extension ``phyelds.accel._engine`` against the active interpreter."""

import argparse
import hashlib
from importlib.machinery import ExtensionFileLoader
from importlib.util import module_from_spec, spec_from_loader
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from types import ModuleType

_LOADED: ModuleType | None = None


def _compiler_command(source: Path, target: Path) -> list[str]:
    compiler = os.environ.get("CC") or sysconfig.get_config_var("CC") or "cc"
    parts = shlex.split(compiler)
    if shutil.which(parts[0]) is None:
        fallback = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if fallback is None:
            raise FileNotFoundError("no C compiler (cc, gcc, clang) found on PATH")
        parts = [fallback]

    include_dir = sysconfig.get_path("include")
    plat_include = sysconfig.get_path("platinclude")
    flags = ["-O3", "-fPIC", "-Wall", "-Wextra", f"-I{include_dir}"]
    if plat_include and plat_include != include_dir:
        flags.append(f"-I{plat_include}")
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        flags.append("-DPy_GIL_DISABLED=1")

    if sys.platform == "darwin":
        link_flags = ["-bundle", "-undefined", "dynamic_lookup"]
    else:
        link_flags = ["-shared"]
    return [*parts, *flags, *link_flags, str(source), "-o", str(target)]


def build_extension(build_dir: Path | None = None) -> Path:
    """Compile ``native/engine.c`` for the running Python interpreter if not already cached.

    Args:
        build_dir: Directory where the compiled extension binary is placed. Defaults to a
            per-user cache directory in the system temporary folder.

    Returns:
        The path of the compiled shared object.

    Raises:
        FileNotFoundError: If no C compiler or Python headers are available.
        subprocess.CalledProcessError: If compilation fails.
    """
    source = Path(__file__).parent / "native" / "engine.c"
    include_header = Path(sysconfig.get_path("include") or "") / "Python.h"
    if not include_header.is_file():
        raise FileNotFoundError(f"Python development headers not found at {include_header}")

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    digest = hashlib.sha256(
        source.read_bytes() + sys.version.encode("utf-8") + ext_suffix.encode("utf-8")
    ).hexdigest()[:12]

    if build_dir is None:
        default_cache = Path(tempfile.gettempdir()) / "phyelds-accel"
        base = Path(os.environ.get("PHYELDS_ACCEL_CACHE", default_cache))
        target_dir = base / digest
    else:
        target_dir = Path(build_dir).resolve()

    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"_engine{ext_suffix}"
    if target.is_file() and build_dir is None:
        return target

    staging = target_dir / f"._engine.{os.getpid()}{ext_suffix}"
    try:
        subprocess.run(
            _compiler_command(source, staging), check=True, capture_output=True, text=True
        )
        staging.replace(target)
    except subprocess.CalledProcessError as err:
        staging.unlink(missing_ok=True)
        raise RuntimeError(f"failed to compile phyelds.accel._engine:\n{err.stderr}") from err
    return target


def load_extension() -> ModuleType:
    """Build (if needed) and import ``phyelds.accel._engine`` once for this interpreter."""
    global _LOADED  # pylint: disable=global-statement
    if _LOADED is not None:
        return _LOADED
    binary = build_extension()
    name = "phyelds.accel._engine"
    loader = ExtensionFileLoader(name, str(binary))
    spec = spec_from_loader(name, loader)
    if spec is None:
        raise ImportError(f"cannot create module spec for {binary}")
    module = module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    _LOADED = module
    return module


def main() -> None:
    """CLI entry point compiling the native extension into ``--build-dir``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=None)
    args = parser.parse_args()
    print(build_extension(args.build_dir))


if __name__ == "__main__":
    main()

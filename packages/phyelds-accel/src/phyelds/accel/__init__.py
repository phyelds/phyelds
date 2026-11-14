"""Optional C-backed engine and runtimes for phyelds aggregate programs."""

from phyelds.accel.build import build_extension, load_extension
from phyelds.accel.runtime import AsynchronousRuntime, SynchronousRuntime, run_round

_EXT = load_extension()
NativeEngine = _EXT.NativeEngine
NativeNodeContext = _EXT.NativeNodeContext

__all__ = [
    "AsynchronousRuntime",
    "NativeEngine",
    "NativeNodeContext",
    "SynchronousRuntime",
    "build_extension",
    "run_round",
]

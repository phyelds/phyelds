"""Unit tests for the C-backed NativeEngine and its build loader."""

import os
import subprocess
import sys
import sysconfig

import pytest

from phyelds import engine
from phyelds.accel import NativeEngine, NativeNodeContext
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.vm.internal import CompactPaths, MutableEngine


@aggregate
def counter() -> int:
    count, set_count = remember(0)
    return set_count(count + 1)


@aggregate
def _branching_counter(flag: bool) -> int:
    if flag:
        return counter()
    return 0


def _compact_key(segments: list[tuple[object, int]]) -> int:
    paths = CompactPaths()
    parent = None
    built: list[int] = []
    for name, idx in segments:
        parent = paths.segment(parent, name, idx)
        built.append(parent)
    return paths.key(built)


def test_native_engine_computes_pinned_compact_keys_bit_for_bit():
    native = NativeEngine()
    engine.set(native)
    native.setup(NativeNodeContext(0, {}))
    first = counter()
    outbox = native.cooldown()
    state = native.state_trace()

    assert first == 1
    assert outbox == {}
    assert state == {598470001: 1}


def test_native_engine_handles_unicode_and_integer_segments_like_mutable_engine():
    native = NativeEngine().setup(NativeNodeContext(0, {}))
    reference = MutableEngine(paths="compact").setup(NativeNodeContext(0, {}))

    for current in (native, reference):
        current.write_state("root", current.current_path())
        current.enter("a")
        current.enter("b")
        inside = current.current_path()
        current.exit()
        current.enter("città")
        current.enter(1)
        current.write_state("numbered", current.current_path())
        current.send("inside", inside)
        current.send("here")

    assert native.state_trace() == reference.state_trace()
    assert native.cooldown() == reference.cooldown()


def test_native_engine_prunes_unread_branch_state_and_supports_forget():
    native = NativeEngine()
    engine.set(native)

    native.setup(NativeNodeContext(0, {}))
    assert _branching_counter(True) == 1
    native.cooldown()
    kept = native.state_trace()

    native.setup(NativeNodeContext(0, {}), {}, kept)
    assert _branching_counter(False) == 0
    native.cooldown()
    after_false = native.state_trace()
    assert after_false == {}

    native.setup(NativeNodeContext(0, {}), {}, after_false)
    assert _branching_counter(True) == 1
    native.enter("temp_slot")
    path = native.current_path()
    native.exit()
    native.write_state("temp", path)
    assert native.key(path) in native.state_trace()
    native.forget(path)
    assert native.key(path) not in native.state_trace()


def test_native_engine_filters_aligned_values_by_current_and_target_path():
    messages = {
        1: {_compact_key([("a", 0)]): "one", _compact_key([("a", 0), ("n", 0)]): "one deeper"},
        2: {_compact_key([("a", 0), ("n", 0)]): "two deeper"},
    }
    native = NativeEngine().setup(NativeNodeContext(0, {}), messages)
    native.enter("a")
    native.enter("n")
    deeper = native.current_path()
    native.exit()

    assert native.aligned() == [1]
    assert native.aligned_values(native.current_path()) == {1: "one"}
    assert native.aligned_values() == {1: "one"}
    assert native.aligned_values(deeper) == {1: "one deeper"}


def test_native_engine_supports_process_transactions():
    native = NativeEngine().setup(NativeNodeContext(0, {}))
    native.enter("root")
    native.enter("before")
    native.exit()

    token = native.begin_process("process:1")
    proc_path = native.current_path()
    native.read_state(proc_path)
    native.write_state("discarded", proc_path)
    native.send("discarded_msg")
    native.end_process(token, False)

    native.enter("after")
    after_path = native.current_path()
    native.exit()
    assert after_path == [
        _compact_key([("root", 0)]),
        _compact_key([("root", 0), ("after", 1)]),
    ]
    assert native.state_trace() == {}
    assert native.cooldown() == {}

    native.setup(NativeNodeContext(0, {}))
    token = native.begin_process("process:2")
    proc_path = native.current_path()
    native.read_state(proc_path)
    native.write_state("kept", proc_path)
    native.send("kept_msg")
    native.end_process(token, True)
    assert native.cooldown() == {_compact_key([("process:2", 0)]): "kept_msg"}
    assert native.state_trace() == {_compact_key([("process:2", 0)]): "kept"}


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded Python"
)
def test_native_extension_keeps_the_gil_disabled():
    environment = {name: value for name, value in os.environ.items() if name != "PYTHON_GIL"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, phyelds.accel; "
            "assert not sys._is_gil_enabled(), 'phyelds.accel enabled the GIL'",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr


def test_native_engine_runs_neighbors_sum():
    native = NativeEngine()
    engine.set(native)

    @aggregate
    def peer_sum() -> int:
        return neighbors(1).sum()

    native.setup(NativeNodeContext(1, {}))
    assert peer_sum() == 1
    sent = native.cooldown()

    native.setup(NativeNodeContext(0, {}), {1: sent})
    assert peer_sum() == 2

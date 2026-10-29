import pytest

from phyelds import engine
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext, MockSimulator


@aggregate
def counter():
    set_count, count = remember(0)
    return set_count(count + 1)


@aggregate
def neighbour_sum():
    set_total, total = remember(0)
    return set_total(neighbors(1).sum() + total)


def _fnv_key(path: list) -> int:
    """The compact key of ``path``, as other runtimes compute it: 30 bits of FNV-1a."""
    digest = 0x811C9DC5
    for byte in "".join(f"{segment}/" for segment in path).encode():
        digest = ((digest ^ byte) * 0x01000193) & 0xFFFFFFFF
    return digest & 0x3FFFFFFF


KEYS = {"debug": str, "compact": _fnv_key}
PATHS = [
    [],
    ["a@0"],
    ["a@0", "b@0"],
    ["a@0", "b@0", "remember@0"],
    ["a@0", "c@2"],
    ["x@3", "y@1"],
    ["città@0", "b@0"],
]


def _state_after_one_round(paths: str) -> dict:
    engine.set(MutableEngine(paths=paths).setup(MockNodeContext(0)))
    counter()
    engine.get().cooldown()
    return engine.get().state_trace()


def test_mutable_engine_uses_readable_keys_by_default():
    engine.set(MutableEngine().setup(MockNodeContext(0)))
    counter()
    engine.get().cooldown()

    assert list(engine.get().state_trace()) == [str(["counter@0", "remember@0"])]


def test_mutable_engine_compact_keys_are_stable_small_integers():
    # Pinned: devices on other runtimes (MicroPython) must compute the same keys.
    assert _state_after_one_round("compact") == {10848852: 1}


def test_mutable_engine_compact_and_debug_paths_compute_the_same_values():
    debug = MockSimulator(3)
    compact = MockSimulator(3, engine_factory=lambda: MutableEngine(paths="compact"))

    debug.cycle_for(neighbour_sum, 4)
    compact.cycle_for(neighbour_sum, 4)

    assert [node.root for node in compact.nodes] == [node.root for node in debug.nodes]
    assert all(isinstance(key, int) for key in compact.nodes[0].context["messages"])


def test_mutable_engine_keys_paths_with_the_encoding_it_is_given():
    codes = {"counter": 1, "remember": 2}

    def numbered(path):
        """``["counter@0", "remember@0"]`` as ``(1, 0, 2, 0)``: readable with ``codes``."""
        key = []
        for segment in path:
            name, counter = segment.rsplit("@", 1)
            key += [codes[name], int(counter)]
        return tuple(key)

    engine.set(MutableEngine(paths=numbered).setup(MockNodeContext(0)))
    counter()

    assert engine.get().state_trace() == {(1, 0, 2, 0): 1}


def test_mutable_engine_rejects_an_unknown_path_mode():
    with pytest.raises(ValueError, match="paths"):
        MutableEngine(paths="short")


@pytest.mark.parametrize("paths", KEYS)
def test_mutable_engine_keys_any_path_as_its_whole_path(paths):
    engine_ = MutableEngine(paths=paths).setup(MockNodeContext(0))
    engine_.enter("a")
    engine_.enter("b")

    for value, path in enumerate(PATHS):
        engine_.write_state(value, path)
    engine_.exit()
    engine_.send("left", PATHS[3])
    engine_.send("here")

    assert engine_.state_trace() == {KEYS[paths](path): value for value, path in enumerate(PATHS)}
    assert engine_.cooldown() == {KEYS[paths](PATHS[3]): "left", KEYS[paths](["a@0"]): "here"}


@pytest.mark.parametrize("paths", KEYS)
def test_mutable_engine_reads_the_messages_of_neighbors_by_whole_path(paths):
    key = KEYS[paths]
    messages = {
        1: {key(["a@0"]): "one", key(["a@0", "n@0"]): "one deeper"},
        2: {key(["a@0", "n@0"]): "two deeper"},
    }
    engine_ = MutableEngine(paths=paths).setup(MockNodeContext(0), messages)
    engine_.enter("a")

    assert engine_.aligned() == [1]
    assert engine_.aligned_values(["a@0"]) == {1: "one"}
    assert engine_.aligned_values(["a@0", "n@0"]) == {1: "one deeper"}


@pytest.mark.parametrize("paths", KEYS)
def test_mutable_engine_keys_paths_made_of_numbers(paths):
    engine_ = MutableEngine(paths=paths).setup(MockNodeContext(0))
    numbered = [[1], [1, 2], ["a@0", 3]]

    for value, path in enumerate(numbered):
        engine_.write_state(value, path)

    assert engine_.state_trace() == {KEYS[paths](path): value for value, path in enumerate(numbered)}

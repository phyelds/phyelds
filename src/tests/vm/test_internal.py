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


def _compact_key(path: list) -> int:
    """
    The compact key of ``path``, a list of ``(name, counter)``, as every runtime must compute
    it: two polynomial hashes, by primes under 2**15, of the bytes of each name and of 256
    plus its counter.
    """
    high, low = 1, 1
    for name, counter in path:
        for byte in str(name).encode():
            high, low = (high * 31 + byte) % 32749, (low * 37 + byte) % 32719
        high, low = (high * 31 + 256 + counter) % 32749, (low * 37 + 256 + counter) % 32719
    return high << 15 | low


def _debug_key(path: list) -> str:
    return str([f"{name}@{counter}" for name, counter in path])


KEYS = {"debug": _debug_key, "compact": _compact_key}


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
    assert _state_after_one_round("compact") == {598470001: 1}
    assert 598470001 < 2**30  # a small integer on 32-bit MicroPython boards


def test_mutable_engine_compact_and_debug_paths_compute_the_same_values():
    debug = MockSimulator(3)
    compact = MockSimulator(3, engine_factory=lambda: MutableEngine(paths="compact"))

    debug.cycle_for(neighbour_sum, 4)
    compact.cycle_for(neighbour_sum, 4)

    assert [node.root for node in compact.nodes] == [node.root for node in debug.nodes]
    assert all(isinstance(key, int) for key in compact.nodes[0].context["messages"])


def test_mutable_engine_keys_paths_with_the_encoding_it_is_given():
    codes = {"counter": 1, "remember": 2}

    class Numbered:
        """Segments as the code of their name and their counter, readable with ``codes``."""

        def segment(self, parent, name, counter):  # pylint: disable=unused-argument
            return f"{codes[name]}.{counter}"

        def key(self, path):
            return "/".join(path)

    engine.set(MutableEngine(paths=Numbered()).setup(MockNodeContext(0)))
    counter()

    assert engine.get().state_trace() == {"1.0/2.0": 1}


def test_mutable_engine_rejects_an_unknown_path_mode():
    with pytest.raises(ValueError, match="paths"):
        MutableEngine(paths="short")


@pytest.mark.parametrize("paths", KEYS)
def test_mutable_engine_keys_the_paths_it_enters(paths):
    engine_ = MutableEngine(paths=paths).setup(MockNodeContext(0))
    engine_.write_state("root", engine_.current_path())
    engine_.enter("a")
    engine_.enter("b")
    inside = engine_.current_path()
    engine_.exit()
    engine_.enter("città")
    engine_.enter(1)  # a number as a name, as in NBR = 1
    engine_.write_state("numbered", engine_.current_path())
    engine_.send("inside", inside)
    engine_.send("here")

    key = KEYS[paths]
    assert engine_.state_trace() == {
        key([]): "root", key([("a", 0), ("città", 1), (1, 0)]): "numbered",
    }
    assert engine_.cooldown() == {
        key([("a", 0), ("b", 0)]): "inside", key([("a", 0), ("città", 1), (1, 0)]): "here",
    }


@pytest.mark.parametrize("paths", KEYS)
def test_mutable_engine_reads_the_messages_of_neighbors_by_path(paths):
    key = KEYS[paths]
    messages = {
        1: {key([("a", 0)]): "one", key([("a", 0), ("n", 0)]): "one deeper"},
        2: {key([("a", 0), ("n", 0)]): "two deeper"},
    }
    engine_ = MutableEngine(paths=paths).setup(MockNodeContext(0), messages)
    engine_.enter("a")
    engine_.enter("n")
    deeper = engine_.current_path()
    engine_.exit()

    assert engine_.aligned() == [1]
    assert engine_.aligned_values(engine_.current_path()) == {1: "one"}
    assert engine_.aligned_values(deeper) == {1: "one deeper"}

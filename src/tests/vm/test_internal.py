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


def test_mutable_engine_rejects_an_unknown_path_mode():
    with pytest.raises(ValueError, match="paths"):
        MutableEngine(paths="short")

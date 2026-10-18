"""Keeps the animations of the library pages reproducible from the programs of the playground."""
import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "animations.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("animations_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


animations = _load_example()


def _results(simulator) -> dict:
    return {node.id: node.data["result"] for node in simulator.environment.nodes.values()}


def test_leaders_scene_splits_the_lattice_into_a_few_clusters():
    simulator = animations.leaders(save=False)

    clusters = set(_results(simulator).values())

    assert 2 <= len(clusters) <= 12


def test_bubbles_scene_ends_with_the_bubble_shut_down():
    simulator = animations.bubbles(save=False)

    results = _results(simulator)

    assert set(results.values()) == {0.0}


def test_corridor_scene_joins_two_opposite_corners_and_leaves_the_other_two_out():
    simulator = animations.corridor(save=False)

    results = _results(simulator)

    assert results[0] and results[143]
    assert not results[11] and not results[132]

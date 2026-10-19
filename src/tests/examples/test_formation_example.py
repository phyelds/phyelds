"""Keeps the formation of the formations page doing what the page says."""
import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "formation.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("formation_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


formation = _load_example()


def test_formation_swarm_takes_each_shape_before_the_next():
    simulator = formation.scene()
    ends = [start - 1 for start, _ in formation.SHAPES[1:]] + [formation.END]

    for end in ends:
        simulator.run(end)
        shape = formation.shape_at(end)
        assert all(shape.inside(node.position) for node in simulator.environment.nodes.values())

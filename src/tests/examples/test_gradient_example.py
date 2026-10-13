"""Keeps the gradient walkthrough of the README and the docs working."""
import importlib.util
from pathlib import Path

import pytest

from phyelds.simulator.runner import schedule_program_for_all

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "gradient.py"
ROUNDS = 12


def _load_example():
    spec = importlib.util.spec_from_file_location("gradient_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gradient = _load_example()


def _results(simulator) -> list[float]:
    return [node.data["result"] for node in simulator.environment.nodes.values()]


def test_hop_gradient_counts_the_hops_from_the_source():
    # 0 - 1 - 2 - 3 - 4, source in 0
    simulator = gradient.deploy_grid(width=5, height=1)
    gradient.set_source(simulator, 0)

    schedule_program_for_all(simulator, 0.0, 1.0, gradient.hop_gradient_program)
    simulator.run(ROUNDS)

    assert _results(simulator) == [0, 1, 2, 3, 4]


def test_metric_gradient_measures_the_euclidean_distance_from_the_source():
    simulator = gradient.deploy_grid(width=5, height=1)
    gradient.set_source(simulator, 0)

    schedule_program_for_all(simulator, 0.0, 1.0, gradient.metric_gradient_program)
    simulator.run(ROUNDS)

    assert _results(simulator) == pytest.approx([0.0, 1.0, 2.0, 3.0, 4.0])


def test_hop_gradient_heals_when_the_source_moves():
    simulator = gradient.deploy_grid(width=5, height=1)
    gradient.set_source(simulator, 0)
    schedule_program_for_all(simulator, 0.0, 1.0, gradient.hop_gradient_program)
    simulator.run(ROUNDS)

    gradient.move_source(simulator, old=0, new=4)
    simulator.run(3 * ROUNDS)

    assert _results(simulator) == [4, 3, 2, 1, 0]

"""Keeps the Mesa example of the docs working."""
import importlib.util
import math
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "mesa_swarm.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("mesa_swarm_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mesa_swarm = _load_example()


def test_swarm_example_builds_a_gradient_from_the_source():
    model = mesa_swarm.Swarm(speed=0.0)

    for _ in range(30):
        model.step()

    assert model.hops[model.source.unique_id] == 0
    for agent in model.agents:
        hops = model.hops[agent.unique_id]
        if 0 < hops < math.inf:
            neighbors = agent.get_neighbors_in_radius(0.3)[0]
            assert min(model.hops[neighbor.unique_id] for neighbor in neighbors) == hops - 1


def test_swarm_example_marks_the_agents_cut_off_from_the_source():
    model = mesa_swarm.Swarm(radius=0.01, speed=0.0)

    model.step()
    model.step()

    cut_off = [agent_id for agent_id, outputs in model.runtime.outputs.items() if outputs["cut_off"]]
    assert sorted(cut_off) == sorted(a.unique_id for a in model.agents if a is not model.source)


def test_swarm_example_runs():
    mesa_swarm.main()

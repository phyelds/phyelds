"""Keeps the mission of the state machine page doing what the page says."""
import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "mission.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("mission_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mission = _load_example()
Phase = mission.Phase
PAGE = Path(__file__).resolve().parents[3] / "docs" / "experimental" / "state-machines.md"


def _states(simulator) -> set:
    return {node.data["result"] for node in simulator.environment.nodes.values()}


def test_mission_drones_agree_on_the_state_before_each_event():
    simulator = mission.scene()
    phases = []
    for until in [time - 1 for time in mission.EVENTS] + [mission.END]:
        simulator.run(until)
        phases.append(_states(simulator))

    assert phases == [{Phase.WAIT}, {Phase.EXPLORE}, {Phase.DEFEND}, {Phase.RESCUE}, {Phase.WAIT}]


def test_mission_defends_the_base_although_the_target_is_found_at_the_same_time():
    simulator = mission.scene()
    attack, safe = 12, 22
    simulator.run(attack - 1)
    seen = set()
    for until in range(attack, safe):
        simulator.run(until)
        seen |= _states(simulator)

    assert Phase.RESCUE in seen
    assert _states(simulator) == {Phase.DEFEND}


def test_mission_drones_head_for_the_base_while_they_defend_it():
    simulator = mission.scene()
    simulator.run(21)

    distances = {node.id: node.data["outputs"]["distance"] for node in simulator.environment.nodes.values()}

    assert _states(simulator) == {Phase.DEFEND}
    assert distances[mission.BASE] == 0.0
    assert distances[mission.TARGET] == max(distances.values())


def test_mission_diagram_on_the_page_is_the_one_of_the_machine():
    assert mission.mission.to_mermaid() in PAGE.read_text()

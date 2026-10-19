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
Mission = mission.Mission


def _states(simulator) -> set:
    return {node.data["result"] for node in simulator.environment.nodes.values()}


def test_mission_drones_agree_on_the_state_before_each_event():
    simulator = mission.scene()
    phases = []
    for until in [time - 1 for time in mission.EVENTS] + [mission.END]:
        simulator.run(until)
        phases.append(_states(simulator))

    assert phases == [{Mission.WAIT}, {Mission.EXPLORE}, {Mission.DEFEND}, {Mission.RESCUE}, {Mission.WAIT}]


def test_mission_defends_the_base_although_the_target_is_found_at_the_same_time():
    simulator = mission.scene()
    attack, safe = 12, 22
    simulator.run(attack - 1)
    seen = set()
    for until in range(attack, safe):
        simulator.run(until)
        seen |= _states(simulator)

    assert Mission.RESCUE in seen
    assert _states(simulator) == {Mission.DEFEND}

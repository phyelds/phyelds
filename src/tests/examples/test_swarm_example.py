"""Keeps the swarm mission of the swarm page doing what the page says."""
import importlib.util
import math
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "swarm.py"
PAGE = Path(__file__).resolve().parents[3] / "docs" / "experimental" / "swarm.md"


def _load_example():
    spec = importlib.util.spec_from_file_location("swarm_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


swarm = _load_example()
Phase = swarm.Phase


def _phases(simulator) -> set:
    return {node.data["result"] for node in simulator.environment.nodes.values()}


def _from_leader(simulator) -> list:
    leader = simulator.environment.nodes[swarm.LEADER].position
    return [math.dist(node.position, leader) for node in simulator.environment.nodes.values()]


def test_swarm_drones_agree_on_the_phase_the_leader_senses():
    simulator = swarm.scene()
    phases = []
    for until in [time - 1 for time in swarm.EVENTS] + [swarm.END]:
        simulator.run(until)
        phases.append(_phases(simulator))

    assert phases == [{Phase.GATHER}, {Phase.CROSS}, {Phase.CIRCLE}]


def test_swarm_drones_gather_around_the_leader_keeping_apart():
    simulator = swarm.scene()
    scattered = max(_from_leader(simulator))
    simulator.run(min(swarm.EVENTS) - 1)

    positions = [node.position for node in simulator.environment.nodes.values()]
    nearest = [min(math.dist(here, there) for there in positions if there is not here) for here in positions]
    assert max(_from_leader(simulator)) < scattered * 0.8
    assert sum(distance > swarm.SPACING / 2 for distance in nearest) >= 0.8 * len(nearest)


def test_swarm_drones_turn_around_the_leader_standing_still():
    simulator = swarm.scene()
    simulator.run(max(swarm.EVENTS) + 10)
    leader = simulator.environment.nodes[swarm.LEADER].position
    far = max(simulator.environment.nodes.values(), key=lambda node: math.dist(node.position, leader))
    before = math.atan2(far.position[1] - leader[1], far.position[0] - leader[0])
    simulator.run(swarm.END)
    after = math.atan2(far.position[1] - leader[1], far.position[0] - leader[0])

    assert simulator.environment.nodes[swarm.LEADER].position == leader
    assert abs(after - before) > 0.2


def test_swarm_diagram_on_the_page_is_the_one_of_the_machine():
    assert swarm.mission.to_mermaid() in PAGE.read_text()

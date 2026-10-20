import pytest

from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.runner import aggregate_program_runner


def _moving(position, velocity, max_speed=None, rounds=3.0):
    simulator = Simulator()
    node = simulator.create_node(position, node_id=0)
    simulator.schedule_event(0.0, aggregate_program_runner, simulator, 1.0, node, lambda: store("velocity", velocity))
    simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=max_speed)
    simulator.run(rounds)
    return node.position


def test_follow_velocity_moves_a_node_by_the_velocity_its_program_stores():
    assert _moving((0.0, 0.0), (1.0, 2.0)) == (3.0, 6.0)


def test_follow_velocity_moves_a_node_in_three_dimensions():
    assert _moving((0.0, 0.0, 1.0), (1.0, 0.0, -0.5)) == (3.0, 0.0, -0.5)


def test_follow_velocity_keeps_the_dimensions_of_the_position():
    # a velocity with a height moves a planar node in the plane
    assert _moving((0.0, 0.0), (1.0, 1.0, 1.0)) == (3.0, 3.0)


def test_follow_velocity_caps_the_speed():
    assert _moving((0.0, 0.0), (3.0, 4.0), max_speed=1.0) == pytest.approx((1.8, 2.4))


def test_follow_velocity_leaves_a_node_without_velocity_still():
    simulator = Simulator()
    node = simulator.create_node((1.0, 1.0), node_id=0)
    simulator.schedule_event(0.0, follow_velocity, simulator, 1.0, node)
    simulator.run(3.0)

    assert node.position == (1.0, 1.0)

import math
import random

import pytest

from phyelds.calculus import aggregate
from phyelds.experimental.swarm import (
    Vector, avoid_obstacles, brownian, explore, go_to, is_close, maintain_trajectory,
    maintain_until, neighbors_vectors, stand_still,
)
from phyelds.libraries.device import store
from phyelds.libraries.time import counter
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import full_neighborhood
from phyelds.simulator.runner import aggregate_program_runner, schedule_program_for_all
from phyelds.vm.device import Device


def _once(program, **sensors):
    device = Device(0, program)
    device.run_round(sensors)
    return device.result


def test_neighbors_vectors_point_from_the_device_to_each_neighbor():
    simulator = Simulator()
    for node_id, position in enumerate([(0, 0), (1, 0), (0, 2, 1)]):
        simulator.create_node(position, node_id=node_id)
    simulator.environment.set_neighborhood_function(full_neighborhood)

    @aggregate
    def program():
        return dict(neighbors_vectors().data)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(2)

    assert simulator.environment.nodes[0].data["result"] == {0: Vector(), 1: Vector(1, 0), 2: Vector(0, 2, 1)}


def test_stand_still_is_zero():
    assert _once(stand_still) == Vector()


def test_brownian_moves_in_a_random_horizontal_direction_of_the_given_length():
    random.seed(1)
    velocities = [_once(lambda: brownian(2.0)) for _ in range(20)]

    assert all(velocity.length() == pytest.approx(2.0) and velocity.z == 0 for velocity in velocities)
    assert len(set(velocities)) == 20


def test_brownian_moves_in_three_dimensions():
    random.seed(1)
    velocities = [_once(lambda: brownian(2.0, dimensions=3)) for _ in range(20)]

    assert all(velocity.length() == pytest.approx(2.0) for velocity in velocities)
    assert any(velocity.z != 0 for velocity in velocities)


def test_go_to_heads_to_the_target_at_the_given_speed():
    velocity = _once(lambda: go_to((3, 4, 0), speed=2.0), position=(0, 0, 0))

    assert tuple(velocity) == pytest.approx((1.2, 1.6, 0.0))


def test_go_to_stands_still_on_the_target():
    assert _once(lambda: go_to((3, 4), speed=2.0), position=(3, 4)) == Vector()


def test_is_close_tells_whether_the_target_is_within_the_distance():
    assert _once(lambda: is_close((3, 4), 5.0), position=(0, 0))
    assert not _once(lambda: is_close((3, 4), 4.9), position=(0, 0))


def test_explore_wanders_inside_the_bounds():
    random.seed(3)
    simulator = Simulator()
    node = simulator.create_node((5.0, 5.0), node_id=0)
    visited = []

    def program():
        store("velocity", explore((0, 0), (10, 10), speed=1.0))
        visited.append(node.position)

    simulator.schedule_event(0.0, aggregate_program_runner, simulator, 1.0, node, program)
    simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node)
    simulator.run(200)

    assert all(-1 <= x <= 11 and -1 <= y <= 11 for x, y in visited)
    assert max(x for x, _ in visited) - min(x for x, _ in visited) > 5


def test_maintain_trajectory_draws_a_new_velocity_every_period():
    device = Device(0, lambda: maintain_trajectory(lambda: Vector(counter(), 0), period=3.0))
    velocities = []
    for time in range(7):
        device.run_round({"time": float(time)})
        velocities.append(device.result.x)

    assert velocities[0:3] == [velocities[0]] * 3
    assert velocities[3:6] == [velocities[3]] * 3
    assert velocities[3] != velocities[0]


def test_maintain_until_stops_when_the_condition_holds():
    assert _once(lambda: maintain_until(Vector(1, 0), False)) == Vector(1, 0)
    assert _once(lambda: maintain_until(Vector(1, 0), True)) == Vector()


def test_avoid_obstacles_points_away_from_the_close_ones():
    velocity = _once(lambda: avoid_obstacles([Vector(1, 0), Vector(0, 5)], min_distance=2.0))

    assert tuple(velocity) == pytest.approx((-0.01, 0.0, 0.0))
    assert math.isclose(velocity.length(), (2.0 - 1.0) / 100)

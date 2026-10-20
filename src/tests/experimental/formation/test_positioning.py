import math
import random

import pytest

from phyelds.experimental.formation import (
    Frame, circle, formation, global_positioning, leader_positioning, place_shape,
)
from phyelds.experimental.swarm import Vector, neighbors_vectors
from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device


def _grid(origin=(10.0, 20.0)):
    simulator = Simulator()
    for node_id in range(9):
        row, column = divmod(node_id, 3)
        simulator.create_node((origin[0] + column, origin[1] + row), node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))
    return simulator


def _frames(simulator, positioning, rounds=10):
    schedule_program_for_all(simulator, 0.0, 1.0, positioning)
    simulator.run(rounds)
    return {node.id: node.data["result"] for node in simulator.environment.nodes.values()}


def test_global_positioning_is_the_position_and_the_vectors_to_the_neighbors():
    frames = _frames(_grid(), global_positioning, rounds=2)

    assert frames[4].position == Vector(11, 21)
    assert sorted(map(tuple, frames[4].offsets)) == [(-1, 0, 0), (0, -1, 0), (0, 1, 0), (1, 0, 0)]
    assert not frames[4].relative


def test_leader_positioning_locates_the_robots_from_the_leader_with_the_lowest_id():
    frames = _frames(_grid(), leader_positioning)

    assert frames[0].is_leader and frames[0].is_reference and frames[0].relative
    assert not any(frames[node_id].is_leader for node_id in range(1, 9))
    assert [tuple(frames[node_id].position)[:2] for node_id in (0, 5, 8)] == [(0, 0), (2, 1), (2, 2)]


def test_leader_positioning_takes_the_displacements_robots_sense():
    # displacements sensed in a frame turned by a quarter turn, as by a compass off by 90°
    frames = _frames(_grid(), lambda: leader_positioning(
        offsets=neighbors_vectors().map(lambda offset: offset.rotate(math.pi / 2))
    ))

    assert tuple(frames[2].position) == pytest.approx((0, 2, 0))


def test_leader_positioning_puts_a_robot_alone_at_the_origin_as_its_own_leader():
    device = Device(1, leader_positioning)
    device.run_round({"position": (7, 7)})

    assert device.result.is_leader and device.result.position == Vector()


def test_place_shape_puts_the_deepest_point_of_the_shape_on_the_leader():
    ring = circle((5, 5), 3).ring(1)
    shapes = {}

    def program():
        frame = leader_positioning()
        shapes[frame.is_leader] = place_shape(frame, ring)

    _frames(_grid(), program)

    assert shapes[True]((0, 0)) == pytest.approx(-1, abs=1e-2)
    assert shapes[False]((0, 0)) == pytest.approx(-1, abs=1e-2)


def test_formation_spreads_a_swarm_around_its_leader():
    random.seed(4)
    simulator = Simulator()
    leader = (30.0, 30.0)
    simulator.create_node(leader, node_id=0)
    for node_id in range(1, 12):
        simulator.create_node((leader[0] + random.uniform(-1, 1), leader[1] + random.uniform(-1, 1)), node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(3.0))
    shape = circle((0, 0), 3)

    def program():
        store("velocity", formation(shape, reach=1.5, positioning=leader_positioning))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=0.3)
    simulator.run(80)
    positions = [Vector(*node.position) - Vector(*leader) for node in simulator.environment.nodes.values()]

    assert simulator.environment.nodes[0].position == leader
    assert all(shape.inside(position) for position in positions)
    assert min(position.length() for position in positions[1:]) > 0.5


def test_frame_is_a_reference_when_it_leads():
    assert Frame(Vector(), is_leader=True).is_reference
    assert not Frame(Vector()).is_reference

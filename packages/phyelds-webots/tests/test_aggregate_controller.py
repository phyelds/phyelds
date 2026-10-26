import math

import pytest

from fakes import World

from phyelds.calculus import aggregate, neighbors
from phyelds.experimental.swarm import neighbors_vectors
from phyelds.libraries.device import local_position, sense, store
from phyelds.libraries.distances import hops_distance, neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time
from phyelds.webots import AggregateController


@aggregate
def hops_to_source():
    distance = distance_to(sense("source"), hops_distance())
    store("near", distance < 2)
    return distance


@aggregate
def metres_to_source():
    return distance_to(sense("source"), neighbors_distances())


@aggregate
def vectors_to_neighbors():
    return {name: tuple(vector) for name, vector in neighbors_vectors().exclude_self().items()}


@aggregate
def where_it_faces():
    return sense("heading")


@aggregate
def neighbour_count():
    return neighbors(1).sum(include_self=False)


@aggregate
def what_it_senses():
    return local_position(), local_time(), sense("battery")


def _run(controllers, world, steps):
    for _ in range(steps):
        world.step()
        results = [controller.run_round() for controller in controllers]
    return results


def test_controller_computes_a_gradient_over_the_radio():
    world = World(radio_range=0.15)
    controllers = [
        AggregateController(robot, hops_to_source, sensors=lambda robot=robot: {"source": robot.name == "robot(0)"})
        for robot in world.line(4)
    ]

    results = _run(controllers, world, steps=6)

    assert results == [0, 1, 2, 3]
    assert [controller.outputs["near"] for controller in controllers] == [True, True, False, False]
    assert controllers[3].result == 3


def test_controller_measures_the_distance_to_its_neighbors_without_a_gps():
    world = World(radio_range=0.15)
    controllers = [
        AggregateController(robot, metres_to_source, sensors=lambda robot=robot: {"source": robot.name == "robot(0)"})
        for robot in world.line(4)
    ]

    results = _run(controllers, world, steps=6)

    assert results == pytest.approx([0.0, 0.1, 0.2, 0.3])


def test_controller_measures_the_vectors_to_its_neighbors_in_the_world_frame():
    world = World(radio_range=0.15)
    robots = world.line(3)
    robots[1].yaw, robots[2].yaw = math.pi / 2, math.pi
    controllers = [AggregateController(robot, vectors_to_neighbors, inertial_unit="inertial unit") for robot in robots]

    vectors = _run(controllers, world, steps=2)[1]

    assert vectors.keys() == {"robot(0)", "robot(2)"}
    assert vectors["robot(0)"] == pytest.approx((-0.1, 0.0, 0.0))
    assert vectors["robot(2)"] == pytest.approx((0.1, 0.0, 0.0))


def test_controller_senses_the_heading_from_the_inertial_unit():
    world = World(radio_range=0.15)
    robot = world.line(1)[0]
    robot.yaw = math.pi / 2
    controller = AggregateController(robot, where_it_faces, inertial_unit="inertial unit")

    heading = _run([controller], world, steps=1)[0]

    assert heading == pytest.approx((0.0, 1.0, 0.0))


def test_controller_forgets_a_robot_out_of_range_after_one_round():
    world = World(radio_range=0.15)
    controllers = [AggregateController(robot, neighbour_count) for robot in world.line(3)]
    assert _run(controllers, world, steps=3) == [1, 2, 1]

    world.robots[2].position = [5, 0, 0]

    assert _run(controllers, world, steps=2) == [1, 1, 0]


def test_controller_senses_time_gps_position_and_extra_sensors():
    world = World(radio_range=0.15)
    robot = world.line(1)[0]
    robot.position = [1.0, 2.0, 0.5]
    controller = AggregateController(robot, what_it_senses, gps="gps", sensors=lambda: {"battery": 0.9})

    position, time, battery = _run([controller], world, steps=2)[0]

    assert position == (1.0, 2.0, 0.5)
    assert time == pytest.approx(0.064)
    assert battery == 0.9
    assert robot.devices["gps"].sampling_period == 32
    assert robot.devices["receiver"].sampling_period == 32


def test_controller_has_no_position_without_a_gps():
    world = World(radio_range=0.15)
    controller = AggregateController(world.line(1)[0], what_it_senses)

    assert _run([controller], world, steps=1)[0][0] is None


def test_controller_rejects_a_missing_device():
    world = World(radio_range=0.15)

    with pytest.raises(ValueError, match="radio"):
        AggregateController(world.line(1)[0], neighbour_count, emitter="radio")

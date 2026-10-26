import math

import pytest

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


class FakeEmitter:
    def __init__(self, world, robot):
        self.world, self.robot = world, robot

    def send(self, data):
        self.world.sent.append((self.robot, bytes(data)))


class FakeReceiver:
    """Queues packets with what Webots measures of their sender: 1/r² and its direction."""

    def __init__(self):
        self.queue, self.sampling_period = [], None

    def enable(self, sampling_period):
        self.sampling_period = sampling_period

    def getQueueLength(self):  # pylint: disable=invalid-name
        return len(self.queue)

    def getBytes(self):  # pylint: disable=invalid-name
        return self.queue[0][0]

    def getSignalStrength(self):  # pylint: disable=invalid-name
        return self.queue[0][1]

    def getEmitterDirection(self):  # pylint: disable=invalid-name
        return list(self.queue[0][2])

    def nextPacket(self):  # pylint: disable=invalid-name
        self.queue.pop(0)


class FakeGPS:
    def __init__(self, robot):
        self.robot, self.sampling_period = robot, None

    def enable(self, sampling_period):
        self.sampling_period = sampling_period

    def getValues(self):  # pylint: disable=invalid-name
        return list(self.robot.position)


class FakeInertialUnit:
    def __init__(self, robot):
        self.robot, self.sampling_period = robot, None

    def enable(self, sampling_period):
        self.sampling_period = sampling_period

    def getQuaternion(self):  # pylint: disable=invalid-name
        return [0.0, 0.0, math.sin(self.robot.yaw / 2), math.cos(self.robot.yaw / 2)]

    def getRollPitchYaw(self):  # pylint: disable=invalid-name
        return [0.0, 0.0, self.robot.yaw]


class FakeRobot:
    """The part of the Webots ``Robot`` the controller uses."""

    def __init__(self, world, name, position):
        self.world, self.name, self.position, self.yaw = world, name, position, 0.0
        self.devices = {
            "emitter": FakeEmitter(world, self), "receiver": FakeReceiver(), "gps": FakeGPS(self),
            "inertial unit": FakeInertialUnit(self),
        }

    def getName(self):  # pylint: disable=invalid-name
        return self.name

    def getBasicTimeStep(self):  # pylint: disable=invalid-name
        return 32.0

    def getTime(self):  # pylint: disable=invalid-name
        return self.world.time

    def getDevice(self, name):  # pylint: disable=invalid-name
        return self.devices.get(name)


class FakeWorld:
    """Webots radio: what is sent in a step reaches, in the next one, the robots in range."""

    def __init__(self, radio_range):
        self.radio_range, self.time, self.sent = radio_range, 0.0, []

    def step(self):
        self.time += 0.032
        for sender, packet in self.sent:
            for robot in self.robots:
                distance = math.dist(robot.position, sender.position)
                if robot is not sender and distance <= self.radio_range:
                    robot.devices["receiver"].queue.append((packet, distance ** -2, _seen_by(robot, sender)))
        self.sent = []

    def line(self, size):
        self.robots = [FakeRobot(self, f"robot({index})", [0.1 * index, 0, 0]) for index in range(size)]
        return self.robots


def _seen_by(robot, sender):
    """The direction of ``sender`` in the frame of ``robot``, turned by its yaw about z."""
    x, y, z = ((there - here) / math.dist(robot.position, sender.position)
               for here, there in zip(robot.position, sender.position))
    cos, sin = math.cos(robot.yaw), math.sin(robot.yaw)
    return [cos * x + sin * y, cos * y - sin * x, z]


def _run(controllers, world, steps):
    for _ in range(steps):
        world.step()
        results = [controller.run_round() for controller in controllers]
    return results


def test_controller_computes_a_gradient_over_the_radio():
    world = FakeWorld(radio_range=0.15)
    controllers = [
        AggregateController(robot, hops_to_source, sensors=lambda robot=robot: {"source": robot.name == "robot(0)"})
        for robot in world.line(4)
    ]

    results = _run(controllers, world, steps=6)

    assert results == [0, 1, 2, 3]
    assert [controller.outputs["near"] for controller in controllers] == [True, True, False, False]
    assert controllers[3].result == 3


def test_controller_measures_the_distance_to_its_neighbors_without_a_gps():
    world = FakeWorld(radio_range=0.15)
    controllers = [
        AggregateController(robot, metres_to_source, sensors=lambda robot=robot: {"source": robot.name == "robot(0)"})
        for robot in world.line(4)
    ]

    results = _run(controllers, world, steps=6)

    assert results == pytest.approx([0.0, 0.1, 0.2, 0.3])


def test_controller_measures_the_vectors_to_its_neighbors_in_the_world_frame():
    world = FakeWorld(radio_range=0.15)
    robots = world.line(3)
    robots[1].yaw, robots[2].yaw = math.pi / 2, math.pi
    controllers = [AggregateController(robot, vectors_to_neighbors, inertial_unit="inertial unit") for robot in robots]

    vectors = _run(controllers, world, steps=2)[1]

    assert vectors.keys() == {"robot(0)", "robot(2)"}
    assert vectors["robot(0)"] == pytest.approx((-0.1, 0.0, 0.0))
    assert vectors["robot(2)"] == pytest.approx((0.1, 0.0, 0.0))


def test_controller_senses_the_heading_from_the_inertial_unit():
    world = FakeWorld(radio_range=0.15)
    robot = world.line(1)[0]
    robot.yaw = math.pi / 2
    controller = AggregateController(robot, where_it_faces, inertial_unit="inertial unit")

    heading = _run([controller], world, steps=1)[0]

    assert heading == pytest.approx((0.0, 1.0, 0.0))


def test_controller_forgets_a_robot_out_of_range_after_one_round():
    world = FakeWorld(radio_range=0.15)
    controllers = [AggregateController(robot, neighbour_count) for robot in world.line(3)]
    assert _run(controllers, world, steps=3) == [1, 2, 1]

    world.robots[2].position = [5, 0, 0]

    assert _run(controllers, world, steps=2) == [1, 1, 0]


def test_controller_senses_time_gps_position_and_extra_sensors():
    world = FakeWorld(radio_range=0.15)
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
    world = FakeWorld(radio_range=0.15)
    controller = AggregateController(world.line(1)[0], what_it_senses)

    assert _run([controller], world, steps=1)[0][0] is None


def test_controller_rejects_a_missing_device():
    world = FakeWorld(radio_range=0.15)

    with pytest.raises(ValueError, match="radio"):
        AggregateController(world.line(1)[0], neighbour_count, emitter="radio")

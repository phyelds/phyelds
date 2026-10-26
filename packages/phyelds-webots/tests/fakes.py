"""
Stand-ins for the Webots devices, named after their classes in the ``controller`` module.

A ``World`` steps the robots as Webots does: what a robot sends in a step reaches, in the
next one, the robots in range, with the strength and direction Webots measures.
"""
import math


class Device:  # pylint: disable=too-few-public-methods
    """A device, named by the robot it is added to."""

    name = None

    def getName(self):  # pylint: disable=invalid-name
        return self.name


class Emitter(Device):
    def __init__(self, world, robot):
        self.world, self.robot = world, robot

    def send(self, data):
        self.world.sent.append((self.robot, bytes(data)))


class Receiver(Device):
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


class GPS(Device):
    def __init__(self, robot):
        self.robot, self.sampling_period = robot, None

    def enable(self, sampling_period):
        self.sampling_period = sampling_period

    def getValues(self):  # pylint: disable=invalid-name
        return list(self.robot.position)


class InertialUnit(Device):
    def __init__(self, robot):
        self.robot, self.sampling_period = robot, None

    def enable(self, sampling_period):
        self.sampling_period = sampling_period

    def getQuaternion(self):  # pylint: disable=invalid-name
        return [0.0, 0.0, math.sin(self.robot.yaw / 2), math.cos(self.robot.yaw / 2)]

    def getRollPitchYaw(self):  # pylint: disable=invalid-name
        return [0.0, 0.0, self.robot.yaw]


class Robot:
    """The part of the Webots ``Robot`` the controller uses."""

    def __init__(self, world, name, position):
        self.world, self.name, self.position, self.yaw = world, name, position, 0.0
        self.devices = {}
        self.add(**{
            "emitter": Emitter(world, self), "receiver": Receiver(), "gps": GPS(self),
            "inertial unit": InertialUnit(self),
        })

    def add(self, **devices):
        """Give the robot ``devices``, by name."""
        for name, device in devices.items():
            device.name = name
            self.devices[name] = device

    def getName(self):  # pylint: disable=invalid-name
        return self.name

    def getBasicTimeStep(self):  # pylint: disable=invalid-name
        return 32.0

    def getTime(self):  # pylint: disable=invalid-name
        return self.world.time

    def getDevice(self, name):  # pylint: disable=invalid-name
        return self.devices.get(name)

    def getNumberOfDevices(self):  # pylint: disable=invalid-name
        return len(self.devices)

    def getDeviceByIndex(self, index):  # pylint: disable=invalid-name
        return list(self.devices.values())[index]


class World:
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
        self.robots = [Robot(self, f"robot({index})", [0.1 * index, 0, 0]) for index in range(size)]
        return self.robots


def _seen_by(robot, sender):
    """The direction of ``sender`` in the frame of ``robot``, turned by its yaw about z."""
    x, y, z = ((there - here) / math.dist(robot.position, sender.position)
               for here, there in zip(robot.position, sender.position))
    cos, sin = math.cos(robot.yaw), math.sin(robot.yaw)
    return [cos * x + sin * y, cos * y - sin * x, z]


class LED(Device):
    """Keeps the value it was set to, as Webots reads it: ``0xRRGGBB``, or an index or an intensity."""

    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class Motor(Device):
    """A wheel: Webots turns it at ``velocity`` once its position is infinite."""

    def __init__(self, max_velocity=100.0):
        self.position, self.velocity, self.max_velocity = 0.0, None, max_velocity

    def setPosition(self, position):  # pylint: disable=invalid-name
        self.position = position

    def setVelocity(self, velocity):  # pylint: disable=invalid-name
        self.velocity = velocity

    def getMaxVelocity(self):  # pylint: disable=invalid-name
        return self.max_velocity

"""The devices of a Webots robot that its program senses and drives."""
import math
from collections.abc import Mapping, Sequence
from typing import Any
from xml.etree import ElementTree

from phyelds.libraries.device import led, obstacle, velocity

WHEELS = ("left wheel motor", "right wheel motor")
"""The names of the wheel motors, as the e-puck, the Elisa-3 and the Khepera name them."""

_STILL = 0.005  # m/s: slower than this, a robot stands still rather than turn on the spot


class Body:
    """
    Senses the surroundings of a Webots robot, and applies the outputs of a program to it.

    Args:
        robot: The ``controller.Robot`` whose devices to drive.
        rgb_leds: Whether the LEDs take any colour (``gradual``, with an empty ``color``
            list). Otherwise they are on, in the first colour of their list, unless the
            program sends black: Webots does not tell a controller which kind they are.
        wheel_radius: The radius of the wheels, in metres, to drive them: Webots turns
            them in rad/s.
        max_speed: The fastest the robot moves, in m/s, whatever velocity the program sends.

    Raises:
        ValueError: If the robot has wheels, but no ``wheel_radius`` or no ``InertialUnit``
            to steer by.
    """

    def __init__(
        self, robot: Any, *, rgb_leds: bool = True, wheel_radius: float | None = None,
        max_speed: float = 0.1,
    ) -> None:
        self._leds = _devices(robot, "LED")
        self._rgb_leds = rgb_leds
        motors = {motor.getName(): motor for motor in _devices(robot, "Motor")}
        self._wheels = [motors[name] for name in WHEELS if name in motors]
        self._wheel_radius, self._max_speed = wheel_radius, max_speed
        self._inertial_unit = next(iter(_devices(robot, "InertialUnit")), None)
        if self._wheels and wheel_radius is None:
            raise ValueError(f"robot {robot.getName()!r} has wheels: give their wheel_radius")
        if self._wheels and self._inertial_unit is None:
            raise ValueError(f"robot {robot.getName()!r} needs an InertialUnit to steer its wheels")
        sensors = _devices(robot, "DistanceSensor")
        directions = _directions(robot.getUrdf()) if sensors else {}
        self._distance_sensors = [(sensor, directions[sensor.getName()]) for sensor in sensors]
        for sensor in [self._inertial_unit, *sensors]:
            if sensor is not None:
                sensor.enable(int(robot.getBasicTimeStep()))
        for wheel in self._wheels:
            wheel.setPosition(math.inf)  # velocity control, which starts at full speed: stop it
            wheel.setVelocity(0.0)

    def sense(self) -> dict[str, Any]:
        """
        What the body senses: ``obstacle``, a vector in the frame of the world.

        Each ``DistanceSensor`` pushes away from where it looks, in the direction its pose
        in the URDF of the robot gives, as much as it sees something close, from 0 at the
        end of its range to 1 touching. Without distance sensors or an ``InertialUnit``,
        ``obstacle`` is ``None``.
        """
        if not self._distance_sensors or self._inertial_unit is None:
            return {obstacle.name: None}
        x = y = 0.0
        for sensor, (look_x, look_y) in self._distance_sensors:
            closeness = _closeness(sensor)
            x, y = x - closeness * look_x, y - closeness * look_y
        yaw = self._inertial_unit.getRollPitchYaw()[2]
        cos, sin = math.cos(yaw), math.sin(yaw)
        return {obstacle.name: (cos * x - sin * y, sin * x + cos * y, 0.0)}

    def act(self, outputs: Mapping[str, Any]) -> None:
        """
        Drive the devices as the program says, in its last round.

        Args:
            outputs: The outputs of the program, such as ``AggregateController.outputs``.
        """
        self._light(led.read(outputs, default=(0, 0, 0)))
        if self._wheels:
            self._drive(velocity.read(outputs, default=(0.0, 0.0)))

    def _light(self, rgb: Sequence[int]) -> None:
        """Light the LEDs with the colour ``rgb``, or switch them on or off."""
        red, green, blue = (int(channel) for channel in rgb)
        colour = red << 16 | green << 8 | blue
        for light in self._leds:
            light.set(colour if self._rgb_leds else int(colour != 0))

    def _drive(self, target: Sequence[float]) -> None:
        """Turn the wheels to take the robot along ``target``, in m/s."""
        yaw = self._inertial_unit.getRollPitchYaw()[2]
        left, right = _wheel_speeds(target, yaw, self._max_speed)
        speeds = [left / self._wheel_radius, right / self._wheel_radius]
        reach = [abs(speed) / wheel.getMaxVelocity() for wheel, speed in zip(self._wheels, speeds)]
        # Webots would cut a wheel alone to its top speed, and so bend the arc: slow both.
        scale = max(1.0, *reach)
        for wheel, speed in zip(self._wheels, speeds):
            wheel.setVelocity(speed / scale)


def _wheel_speeds(target: Sequence[float], yaw: float, max_speed: float) -> tuple[float, float]:
    """
    The speeds of the left and right wheel, in m/s, that take a robot along ``target``.

    As in ARGoS, the robot turns towards the target velocity, in the frame of the world, and
    drives forward as much as it already faces it, never backwards, at most at ``max_speed``.
    """
    x, y, *_ = target
    speed = min(math.hypot(x, y), max_speed)
    if speed < _STILL:
        return 0.0, 0.0
    angle = math.remainder(math.atan2(y, x) - yaw, math.tau)
    forward, turn = speed * max(0.0, math.cos(angle)), speed * angle
    return forward - turn, forward + turn


def _closeness(sensor: Any) -> float:
    """
    How close what ``sensor`` sees is: 1 at the start of its lookup table, 0 at its end.

    The value goes back to a distance through the lookup table, which is far from linear on
    infra-red sensors, and the closeness is linear in that distance.
    """
    table = sensor.getLookupTable()
    rows = sorted(zip(table[0::3], table[1::3]))
    (nearest, nearest_value), (farthest, farthest_value) = rows[0], rows[-1]
    value = sensor.getValue()
    for (near, near_value), (far, far_value) in zip(rows, rows[1:]):
        between = min(near_value, far_value) <= value <= max(near_value, far_value)
        if between and near_value != far_value:
            distance = near + (far - near) * (value - near_value) / (far_value - near_value)
            return 1.0 - (distance - nearest) / (farthest - nearest)
    # Beyond the table: as close as it reads, or as far.
    return float(abs(value - nearest_value) < abs(value - farthest_value))


def _directions(urdf: str) -> dict[str, tuple[float, float]]:
    """
    Where each link of a URDF looks along its x axis, as Webots points its distance sensors.

    The direction is horizontal, in the frame of the robot: the x axis of the link turned by
    the joints from it up to the root.
    """
    joints = {
        joint.find("child").get("link"): (joint.find("parent").get("link"), _origin(joint))
        for joint in ElementTree.fromstring(urdf).iter("joint")
    }
    directions = {}
    for link in joints:
        look, above = (1.0, 0.0, 0.0), link
        while above in joints:
            above, rotation = joints[above]
            look = tuple(sum(row[i] * look[i] for i in range(3)) for row in rotation)
        directions[link] = look[0], look[1]
    return directions


def _origin(joint: ElementTree.Element) -> tuple[tuple[float, ...], ...]:
    """The rotation of a URDF joint, from its roll, pitch and yaw: Rz(yaw) Ry(pitch) Rx(roll)."""
    origin = joint.find("origin")
    rpy = "0 0 0" if origin is None else origin.get("rpy", "0 0 0")
    roll, pitch, yaw = map(float, rpy.split())
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def _devices(robot: Any, kind: str) -> list[Any]:
    """The devices of ``robot`` whose class in the ``controller`` module is ``kind``."""
    devices = (robot.getDeviceByIndex(index) for index in range(robot.getNumberOfDevices()))
    return [device for device in devices if type(device).__name__ == kind]

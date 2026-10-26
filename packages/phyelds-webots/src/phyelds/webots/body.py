"""The devices of a Webots robot that its program drives."""
import math
from collections.abc import Mapping, Sequence
from typing import Any

from phyelds.libraries.device import led, velocity

WHEELS = ("left wheel motor", "right wheel motor")
"""The names of the wheel motors, as the e-puck, the Elisa-3 and the Khepera name them."""

_STILL = 0.005  # m/s: slower than this, a robot stands still rather than turn on the spot


class Body:  # pylint: disable=too-few-public-methods
    """
    Applies the outputs of a program to the devices of a Webots robot.

    Args:
        robot: The ``controller.Robot`` whose devices to drive.
        rgb_leds: Whether the LEDs take any colour (``gradual``, with an empty ``color``
            list). Otherwise they are on, in the first colour of their list, unless the
            program sends black: Webots does not tell a controller which kind they are.
        wheel_radius: The radius of the wheels, in metres, to drive them: Webots turns
            them in rad/s.

    Raises:
        ValueError: If the robot has wheels, but no ``wheel_radius`` or no ``InertialUnit``
            to steer by.
    """

    def __init__(
        self, robot: Any, *, rgb_leds: bool = True, wheel_radius: float | None = None
    ) -> None:
        self._leds = _devices(robot, "LED")
        self._rgb_leds = rgb_leds
        motors = {motor.getName(): motor for motor in _devices(robot, "Motor")}
        self._wheels = [motors[name] for name in WHEELS if name in motors]
        self._wheel_radius = wheel_radius
        self._inertial_unit = next(iter(_devices(robot, "InertialUnit")), None)
        if self._wheels and wheel_radius is None:
            raise ValueError(f"robot {robot.getName()!r} has wheels: give their wheel_radius")
        if self._wheels and self._inertial_unit is None:
            raise ValueError(f"robot {robot.getName()!r} needs an InertialUnit to steer its wheels")
        if self._inertial_unit is not None:
            self._inertial_unit.enable(int(robot.getBasicTimeStep()))
        for wheel in self._wheels:
            wheel.setPosition(math.inf)  # velocity control, which starts at full speed: stop it
            wheel.setVelocity(0.0)

    def act(self, outputs: Mapping[str, Any]) -> None:
        """
        Drive the devices as the program says, in its last round.

        Args:
            outputs: The outputs of the program, such as ``AggregateController.outputs``.
        """
        red, green, blue = (int(channel) for channel in led.read(outputs, default=(0, 0, 0)))
        colour = red << 16 | green << 8 | blue
        for light in self._leds:
            light.set(colour if self._rgb_leds else int(colour != 0))
        if self._wheels:
            yaw = self._inertial_unit.getRollPitchYaw()[2]
            speeds = _wheel_speeds(velocity.read(outputs, default=(0.0, 0.0)), yaw)
            for wheel, speed in zip(self._wheels, speeds):
                wheel.setVelocity(speed / self._wheel_radius)


def _wheel_speeds(target: Sequence[float], yaw: float) -> tuple[float, float]:
    """
    The speeds of the left and right wheel, in m/s, that take a robot along ``target``.

    As in ARGoS, the robot turns towards the target velocity, in the frame of the world, and
    drives forward as much as it already faces it, never backwards.
    """
    x, y, *_ = target
    speed = math.hypot(x, y)
    if speed < _STILL:
        return 0.0, 0.0
    angle = math.remainder(math.atan2(y, x) - yaw, math.tau)
    forward, turn = speed * max(0.0, math.cos(angle)), speed * angle
    return forward - turn, forward + turn


def _devices(robot: Any, kind: str) -> list[Any]:
    """The devices of ``robot`` whose class in the ``controller`` module is ``kind``."""
    devices = (robot.getDeviceByIndex(index) for index in range(robot.getNumberOfDevices()))
    return [device for device in devices if type(device).__name__ == kind]

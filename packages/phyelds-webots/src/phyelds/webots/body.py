"""The devices of a Webots robot that its program drives."""
from collections.abc import Mapping
from typing import Any

from phyelds.libraries.device import led


class Body:  # pylint: disable=too-few-public-methods
    """
    Applies the outputs of a program to the devices of a Webots robot.

    Args:
        robot: The ``controller.Robot`` whose devices to drive.
        rgb_leds: Whether the LEDs take any colour (``gradual``, with an empty ``color``
            list). Otherwise they are on, in the first colour of their list, unless the
            program sends black: Webots does not tell a controller which kind they are.
    """

    def __init__(self, robot: Any, *, rgb_leds: bool = True) -> None:
        self._leds = _devices(robot, "LED")
        self._rgb_leds = rgb_leds

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


def _devices(robot: Any, kind: str) -> list[Any]:
    """The devices of ``robot`` whose class in the ``controller`` module is ``kind``."""
    devices = (robot.getDeviceByIndex(index) for index in range(robot.getNumberOfDevices()))
    return [device for device in devices if type(device).__name__ == kind]

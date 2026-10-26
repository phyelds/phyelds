"""The devices of a Webots robot that its program drives."""
from collections.abc import Mapping
from typing import Any

from phyelds.libraries.device import led


class Body:  # pylint: disable=too-few-public-methods
    """
    Applies the outputs of a program to the devices of a Webots robot.

    Args:
        robot: The ``controller.Robot`` whose devices to drive.
    """

    def __init__(self, robot: Any) -> None:
        self._leds = _devices(robot, "LED")

    def act(self, outputs: Mapping[str, Any]) -> None:
        """
        Drive the devices as the program says, in its last round.

        Args:
            outputs: The outputs of the program, such as ``AggregateController.outputs``.
        """
        red, green, blue = (int(channel) for channel in led.read(outputs, default=(0, 0, 0)))
        for light in self._leds:
            light.set(red << 16 | green << 8 | blue)


def _devices(robot: Any, kind: str) -> list[Any]:
    """The devices of ``robot`` whose class in the ``controller`` module is ``kind``."""
    devices = (robot.getDeviceByIndex(index) for index in range(robot.getNumberOfDevices()))
    return [device for device in devices if type(device).__name__ == kind]

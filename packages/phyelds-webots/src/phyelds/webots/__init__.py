"""
Run phyelds programs on the robots of a [Webots](https://cyberbotics.com) simulation.

Each robot runs its own controller, so each robot is a device: its messages travel as bytes
from its ``Emitter`` to the ``Receiver`` of the robots in range.
"""
import json
from collections.abc import Callable, Mapping
from typing import Any

from phyelds.vm.device import Device

__all__ = ["AggregateController"]


class AggregateController:
    """
    Runs an aggregate program on a Webots robot, one round per simulation step.

    The device id is the name of the robot, so robots must have unique names. The neighbors
    of a robot are the robots its ``Emitter`` reaches; Webots delivers a message in the step
    after it was sent, so with a round at every step of every robot the rounds are
    synchronous. The radio measures how far each neighbor is, so ``neighbors_distances()``
    needs no positions.

    Args:
        robot: The ``controller.Robot`` of this controller.
        program: The ``@aggregate`` function to run.
        emitter: The name of the ``Emitter`` device of the robot.
        receiver: The name of the ``Receiver`` device of the robot.
        gps: The name of a ``GPS`` device, whose values become the ``position`` sensor.
        sensors: Extra sensors, read at each round, added to ``time`` (the simulation time),
            ``position`` and ``neighbors_distances`` (from neighbor name to metres).
        paths: The path mode of the engine, ``"debug"`` or ``"compact"``: the same on
            every robot.

    Raises:
        ValueError: If the robot has no device with one of the given names.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        robot: Any,
        program: Callable[[], Any],
        *,
        emitter: str = "emitter",
        receiver: str = "receiver",
        gps: str | None = None,
        sensors: Callable[[], Mapping[str, Any]] | None = None,
        paths: str = "debug",
    ):
        self.robot = robot
        self.sensors = sensors
        self._device = Device(robot.getName(), program, paths=paths)
        self._emitter = _get_device(robot, emitter)
        self._receiver = _get_device(robot, receiver)
        self._gps = None if gps is None else _get_device(robot, gps)
        time_step = int(robot.getBasicTimeStep())
        self._receiver.enable(time_step)
        if self._gps is not None:
            self._gps.enable(time_step)

    @property
    def result(self) -> Any:
        """The value the program computed in the last round."""
        return self._device.result

    @property
    def outputs(self) -> dict[str, Any]:
        """What the program stored with ``store`` in the last round."""
        return self._device.outputs

    def run_round(self) -> Any:
        """
        Run the program once: read the messages received, compute, and send.

        Call it after each ``robot.step``.

        Returns:
            The value the program computed.
        """
        distances = {}
        while self._receiver.getQueueLength() > 0:
            header, _, payload = self._receiver.getBytes().partition(b"\n")
            sender = json.loads(header)
            # Webots gives the signal strength of a packet as 1/r², r the distance from its emitter.
            distances[sender] = self._receiver.getSignalStrength() ** -0.5
            self._device.receive(sender, payload)
            self._receiver.nextPacket()
        payload = self._device.run_round(self._sense(distances))
        self._emitter.send(json.dumps(self._device.device_id).encode() + b"\n" + payload)
        return self.result

    def _sense(self, distances: dict[Any, float]) -> dict[str, Any]:
        """The sensors of this round, given the distances to the robots heard in it."""
        position = None if self._gps is None else tuple(self._gps.getValues())
        sensors = {
            "position": position, "time": self.robot.getTime(), "neighbors_distances": distances,
        }
        if self.sensors is not None:
            sensors.update(self.sensors())
        return sensors


def _get_device(robot: Any, name: str) -> Any:
    """The device ``name`` of ``robot``."""
    device = robot.getDevice(name)
    if device is None:
        raise ValueError(f"robot {robot.getName()!r} has no device named {name!r}")
    return device

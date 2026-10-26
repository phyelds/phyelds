"""
Device library: what a device knows about itself, its sensors and its outputs.

A ``Sensor`` or an ``Actuator`` names a sensor or an output once: the program and its
host share the object, rather than repeating a string that nobody checks.
"""
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Generic, Tuple, TypeVar

from phyelds import engine

T = TypeVar("T")


def local_id() -> int:
    """
    Return the ID of the current device.

    Returns:
        The ID of the device running the program.
    """
    return engine.get().node_context.node_id


def sense(sensor: str) -> Any:
    """
    Read a sensor of the current device.

    Args:
        sensor: The name of the sensor.

    Returns:
        The value of the sensor.
    """
    return engine.get().node_context.sense(sensor)


def local_position() -> Tuple[float, float]:
    """
    Return the position of the current device.

    Returns:
        The position of the device, as given by its ``"position"`` sensor.
    """
    return engine.get().node_context.position()


def store(output: str, value: Any) -> None:
    """
    Write an output of the current device, replacing its previous value.

    Outputs leave the program: the simulator, for instance, collects them in each
    node's ``"outputs"``.

    Args:
        output: The name of the output.
        value: The value to store.
    """
    engine.get().node_context.store(output, value)


class Sensor(Generic[T]):  # pylint: disable=too-few-public-methods
    """
    A sensor of the devices, by name: ``source = Sensor("source")``, then ``source.sense()``.

    Args:
        name: The name the host gives the sensor.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def sense(self) -> T:
        """The value of the sensor on the current device."""
        return sense(self.name)


class Actuator(Generic[T]):
    """
    An actuator of the devices: the program sends it a value, the host reads it.

    The value is an output (see ``store``): it holds until the next round of the
    device, which sends another one, or none.

    Args:
        name: The name of the output.
        check: Whether a value is valid, if only some are: ``send`` refuses the others.
    """

    def __init__(self, name: str, check: Callable[[T], bool] | None = None) -> None:
        self.name = name
        self._check = check

    def send(self, value: T) -> T:
        """
        Send ``value`` to the actuator of the current device.

        Args:
            value: What the actuator does, in this round.

        Returns:
            ``value``, so that a program can return what it does: ``return velocity.send(v)``.

        Raises:
            ValueError: If the check of the actuator refuses ``value``.
        """
        if self._check is not None and not self._check(value):
            raise ValueError(f"{self.name} cannot take {value!r}")
        store(self.name, value)
        return value

    def read(self, outputs: Mapping[str, Any], default: T | None = None) -> T | None:
        """What a program sent, among the ``outputs`` of its device; ``default`` if nothing."""
        return outputs.get(self.name, default)


def _finite_numbers(value: Any) -> bool:
    """Whether ``value`` is a sequence of finite numbers, such as a tuple or a ``Vector``."""
    try:
        return all(not isinstance(each, (str, bool)) and math.isfinite(each) for each in value)
    except TypeError:
        return False


velocity: Actuator[Sequence[float]] = Actuator("velocity", check=_finite_numbers)
"""Where the device moves, and how fast: a sequence of finite numbers, one per axis."""

source: Sensor[bool] = Sensor("source")
"""Whether the device is the source its host is configured with; false if none is."""

heading: Sensor[tuple[float, float, float]] = Sensor("heading")
"""Where the device faces: a horizontal unit vector, in the frame of the world."""

obstacle: Sensor[tuple[float, float, float] | None] = Sensor("obstacle")
"""Away from what the proximity sensors of the device see; ``None`` without them."""

led: Actuator[Sequence[int]] = Actuator("led")
"""The colour of the LEDs of the device: three integer RGB channels, 0–255."""

label: Actuator[str] = Actuator("label")
"""A text about the device, which its host shows or logs."""

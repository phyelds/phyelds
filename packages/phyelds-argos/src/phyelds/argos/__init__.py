"""
ARGoS integration: the sensors and actuators the host gives every robot, named once.

A program reads ``source.sense()`` and sends ``led.send((255, 0, 0))``, rather than
repeating the names the native host uses. Build the host with
``python -m phyelds.argos.build``.
"""
from collections.abc import Sequence

from phyelds.libraries.device import Actuator, Sensor, velocity

__all__ = ["heading", "label", "led", "obstacle", "source", "time", "velocity"]

time: Sensor[float] = Sensor("time")
"""The simulation time, in seconds."""

source: Sensor[bool] = Sensor("source")
"""Whether the robot's ID is the ``source`` of the controller's params; false if omitted."""

heading: Sensor[tuple[float, float, float]] = Sensor("heading")
"""Where the robot faces: a unit vector in the global compass frame."""

obstacle: Sensor[tuple[float, float, float] | None] = Sensor("obstacle")
"""Away from what the proximity sensors or rangefinders see; ``None`` without them."""

led: Actuator[Sequence[int]] = Actuator("led")
"""The colour of the robot's LEDs: three integer RGB channels, 0–255."""

label: Actuator[str] = Actuator("label")
"""The text above the robot in the GUI, and in the final log."""

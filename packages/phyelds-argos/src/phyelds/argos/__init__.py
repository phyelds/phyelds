"""
ARGoS integration: the sensors and actuators the host gives every robot, named once.

A program reads ``source.sense()`` and sends ``led.send((255, 0, 0))``, rather than
repeating the names the native host uses. Build the host with
``python -m phyelds.argos.build``.
"""
from phyelds.libraries.device import Sensor, heading, label, led, obstacle, source, velocity

__all__ = ["heading", "label", "led", "obstacle", "source", "time", "velocity"]

time: Sensor[float] = Sensor("time")
"""The simulation time, in seconds."""

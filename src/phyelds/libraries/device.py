"""
Device library: what a device knows about itself, its sensors and its outputs.
"""
from typing import Any, Tuple
from phyelds import engine


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

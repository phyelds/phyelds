"""
Device library:
Set of function used to get the device information.
"""
from typing import Any, Tuple
from phyelds import engine


def local_id() -> int:
    """
    Get the local id of the device.
    :return:
    """
    return engine.get().node_context.node_id


def sense(sensor: str) -> Any:
    """
    Get the value of the sensor.
    :param sensor: The name of the sensor.
    :return: The value of the sensor.
    """
    return engine.get().node_context.sense(sensor)


def local_position() -> Tuple[float, float]:
    """
    Get the position of the device.
    :return: The position of the device.
    """
    return engine.get().node_context.position()


def store(output: str, value: Any) -> None:
    """
    Store the value in the context.
    :param output: The name of the stored value.
    :param value: The value to be stored.
    :return:
    """
    engine.get().node_context.store(output, value)

"""
Device library:
Set of function used to get the device information.
"""
from phyelds import engine


def local_id():
    """
    Get the local id of the device.
    :return:
    """
    return engine.get().node_context.node_id


def sense(sensor: str) -> any:
    """
    Get the value of the sensor.
    :param sensor: The name of the sensor.
    :return: The value of the sensor.
    """
    return engine.get().node_context.sense(sensor)


def local_position():
    """
    Get the position of the device.
    :return: The position of the device.
    """
    return engine.get().node_context.position()


def store(output: str, value: any):
    """
    Store the value in the context.
    :param output: The name of the stored value.
    :param value: The value to be stored.
    :return:
    """
    engine.get().node_context.store(output, value)

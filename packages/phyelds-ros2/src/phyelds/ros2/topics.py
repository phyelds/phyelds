"""
Which topics a node reads its sensors from, and writes the outputs of its program to.

A ``SensorTopic`` turns each message of a topic into sensors of the program; an
``ActuatorTopic`` turns an output of the program into a message. Message types are named as
ROS names them, ``"package/msg/Type"``, and the conversions see only the fields of the
messages, so a robot of any kind is wired with the presets below, or with conversions of
one's own.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from phyelds.ros2.motion import body_velocity, heading_of, twist, yaw_of, yaw_of_heading


@dataclass(frozen=True)
class SensorTopic:
    """
    A topic whose messages the node senses.

    Attributes:
        topic: The topic, relative to the namespace of the robot unless absolute.
        message_type: Its type, as ``"package/msg/Type"``.
        read: From a message, the sensors it gives, by name; they hold until the next one.
    """

    topic: str
    message_type: str
    read: Callable[[Any], Mapping[str, Any]]


@dataclass(frozen=True)
class ActuatorTopic:
    """
    A topic the node publishes an output of its program on, after each round.

    Attributes:
        output: The output of the program, such as ``"velocity"``.
        topic: The topic, relative to the namespace of the robot unless absolute.
        message_type: Its type, as ``"package/msg/Type"``.
        write: Fills a new message from the value of the output and the latest sensors;
            returns whether to publish it. Nothing is published in a round without the output.
    """

    output: str
    topic: str
    message_type: str
    write: Callable[[Any, Any, Mapping[str, Any]], bool]


def odometry(topic: str = "odom") -> SensorTopic:
    """
    The ``position`` and ``heading`` of the robot, from a ``nav_msgs/Odometry``.

    Args:
        topic: The odometry topic.

    Returns:
        The sensor topic.
    """
    def read(message: Any) -> dict[str, Any]:
        position, orientation = message.pose.pose.position, message.pose.pose.orientation
        angle = yaw_of(orientation.x, orientation.y, orientation.z, orientation.w)
        return {"position": (position.x, position.y, position.z), "heading": heading_of(angle)}

    return SensorTopic(topic, "nav_msgs/msg/Odometry", read)


def turtle_pose(topic: str = "pose") -> SensorTopic:
    """
    The ``position`` and ``heading`` of a turtle of turtlesim, from a ``turtlesim/Pose``.

    Args:
        topic: The pose topic.

    Returns:
        The sensor topic.
    """
    def read(message: Any) -> dict[str, Any]:
        return {"position": (message.x, message.y, 0.0), "heading": heading_of(message.theta)}

    return SensorTopic(topic, "turtlesim/msg/Pose", read)


def reading(name: str, topic: str, message_type: str, *, field: str = "data") -> SensorTopic:
    """
    One field of the messages of a topic, as the sensor ``name``.

    Args:
        name: The name of the sensor, as the program senses it.
        topic: The topic.
        message_type: Its type, as ``"package/msg/Type"``.
        field: The field of the message, ``data`` for the types of ``std_msgs``.

    Returns:
        The sensor topic.
    """
    return SensorTopic(topic, message_type, lambda message: {name: getattr(message, field)})


def differential_drive(
    topic: str = "cmd_vel", *, max_speed: float = 0.2, turn_rate: float = 1.0
) -> ActuatorTopic:
    """
    The ``velocity`` of the program, as the twist of a robot that turns to move, such as a
    differential drive or a car.

    As on Webots and ARGoS, the robot turns towards the velocity, in the frame of the world,
    and drives forward as much as it already faces it. Nothing is sent before the
    ``heading`` is sensed.

    Args:
        topic: The ``geometry_msgs/Twist`` topic.
        max_speed: The fastest the robot moves forward, in m/s.
        turn_rate: How fast it turns, in rad/s for each radian it is off the velocity.

    Returns:
        The actuator topic.
    """
    def write(message: Any, value: Any, sensors: Mapping[str, Any]) -> bool:
        heading = sensors.get("heading")
        if heading is None:
            return False
        message.linear.x, message.angular.z = twist(
            value, yaw=yaw_of_heading(heading), max_speed=max_speed, turn_rate=turn_rate
        )
        return True

    return ActuatorTopic("velocity", topic, "geometry_msgs/msg/Twist", write)


def holonomic_drive(topic: str = "cmd_vel", *, max_speed: float = 0.2) -> ActuatorTopic:
    """
    The ``velocity`` of the program, as the twist of a robot that moves in any direction,
    such as one with omni wheels: in the frame of the robot, without turning.

    Nothing is sent before the ``heading`` is sensed.

    Args:
        topic: The ``geometry_msgs/Twist`` topic.
        max_speed: The fastest the robot moves, in m/s.

    Returns:
        The actuator topic.
    """
    def write(message: Any, value: Any, sensors: Mapping[str, Any]) -> bool:
        heading = sensors.get("heading")
        if heading is None:
            return False
        message.linear.x, message.linear.y = body_velocity(
            value, yaw=yaw_of_heading(heading), max_speed=max_speed
        )
        return True

    return ActuatorTopic("velocity", topic, "geometry_msgs/msg/Twist", write)


def text(output: str = "label", topic: str = "label") -> ActuatorTopic:
    """
    An output of the program as text, on a ``std_msgs/String``.

    Args:
        output: The output, ``label`` by default.
        topic: The topic.

    Returns:
        The actuator topic.
    """
    def write(message: Any, value: Any, _sensors: Mapping[str, Any]) -> bool:
        message.data = str(value)
        return True

    return ActuatorTopic(output, topic, "std_msgs/msg/String", write)


def command(output: str, topic: str, message_type: str, *, field: str = "data") -> ActuatorTopic:
    """
    An output of the program, as it is, in one field of the messages of a topic.

    Args:
        output: The output of the program.
        topic: The topic.
        message_type: Its type, as ``"package/msg/Type"``.
        field: The field of the message, ``data`` for the types of ``std_msgs``.

    Returns:
        The actuator topic.
    """
    def write(message: Any, value: Any, _sensors: Mapping[str, Any]) -> bool:
        setattr(message, field, value)
        return True

    return ActuatorTopic(output, topic, message_type, write)

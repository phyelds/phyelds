"""
A ROS 2 node that runs an aggregate program on its robot: ``python -m phyelds.ros2``.

The node lives in the namespace of its robot. It senses the topics of its ``SensorTopic``s,
publishes the outputs of its program on those of its ``ActuatorTopic``s, and shares one
absolute topic with the other nodes for its messages. ``rclpy`` comes with ROS 2, and is
imported only here.
"""
import argparse
import importlib
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from phyelds.ros2.aggregate_node import AggregateNode
from phyelds.ros2.neighbourhood import Neighbourhood, Reachable, Transforms, WithinRange
from phyelds.ros2.topics import (
    ActuatorTopic,
    SensorTopic,
    differential_drive,
    holonomic_drive,
    laser_obstacle,
    odometry,
    text,
    turtle_pose,
)

TOPIC = "/phyelds/messages"
"""The topic all the nodes share, by default."""

SENSES = {"odom": odometry, "turtlesim": turtle_pose, "scan": laser_obstacle}
"""The sensor topics the command line names, with ``--sense``."""

ACTS = ("differential", "holonomic", "label")
"""The actuator topics the command line names, with ``--act``."""

NEIGHBOURHOODS = ("reachable", "range", "tf")
"""The neighbourhoods the command line names, with ``--neighbourhood``."""


class AggregateRosNode:  # pylint: disable=too-few-public-methods
    """
    A ROS 2 node that runs an aggregate program, one round at each tick of its timer.

    The rounds follow the clock of the node, so they follow the simulation with ``use_sim_time``.

    Args:
        program: The ``@aggregate`` function to run.
        node_name: The name of the node.
        namespace: The namespace of the node, that of its robot; that of the command line if
            ``None``.
        device_id: The id of the robot; its namespace without slashes, or the node name in
            the root namespace, if ``None``.
        neighbourhood: Which senders are neighbours, or a function of the ``rclpy`` node that
            builds the strategy, for one that needs the node, such as ``Transforms`` with
            ``tf_locator``; ``Reachable()`` by default.
        sensor_topics: The topics to sense; ``odometry()`` if ``None``.
        actuator_topics: The topics to act on; ``differential_drive()`` and ``text()`` if
            ``None``.
        sensors: Extra sensors, read at each round.
        period: The time between two rounds, in seconds.
        topic: The topic all the nodes share.
        paths: The path mode of the engine: the same on every node.
        lifetime: For how many rounds the message of a silent neighbour is kept.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        program: Callable[[], Any],
        *,
        node_name: str = "phyelds",
        namespace: str | None = None,
        device_id: str | None = None,
        neighbourhood: Neighbourhood | Callable[[Any], Neighbourhood] | None = None,
        sensor_topics: Iterable[SensorTopic] | None = None,
        actuator_topics: Iterable[ActuatorTopic] | None = None,
        sensors: Callable[[], Mapping[str, Any]] | None = None,
        period: float = 0.1,
        topic: str = TOPIC,
        paths: str = "compact",
        lifetime: int = 2,
    ):
        # pylint: disable=import-error,import-outside-toplevel
        from rclpy.node import Node
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from std_msgs.msg import UInt8MultiArray

        self.node = Node(node_name) if namespace is None else Node(node_name, namespace=namespace)
        if neighbourhood is not None and not hasattr(neighbourhood, "admit"):
            neighbourhood = neighbourhood(self.node)
        self.aggregate = AggregateNode(
            device_id or self.node.get_namespace().strip("/") or self.node.get_name(),
            program, neighbourhood=neighbourhood, sensors=sensors, paths=paths, lifetime=lifetime,
        )
        self.rounds = 0
        """How many rounds the node has run."""
        self._messages = UInt8MultiArray
        # Messages are sent again at each round: a lost one is not worth waiting for.
        qos = QoSProfile(depth=100, reliability=ReliabilityPolicy.BEST_EFFORT)
        self._outbox = self.node.create_publisher(UInt8MultiArray, topic, qos)
        self.node.create_subscription(UInt8MultiArray, topic, self._hear, qos)
        for sensor in [odometry()] if sensor_topics is None else sensor_topics:
            self.node.create_subscription(
                _message_type(sensor.message_type), sensor.topic,
                lambda message, read=sensor.read: self._sense(read, message), 10,
            )
        actuators = [differential_drive(), text()] if actuator_topics is None else actuator_topics
        self._actuators = []
        for actuator in actuators:
            message_type = _message_type(actuator.message_type)
            publisher = self.node.create_publisher(message_type, actuator.topic, 10)
            self._actuators.append((actuator, message_type, publisher))
        self.node.create_timer(period, self.run_round)

    def run_round(self) -> None:
        """Run the program once, publish its message, and act on its outputs."""
        time = self.node.get_clock().now().nanoseconds / 1e9
        message = self._messages()
        message.data = self.aggregate.run_round(time)
        self._outbox.publish(message)
        self.rounds += 1
        for actuator, message_type, publisher in self._actuators:
            value = self.aggregate.outputs.get(actuator.output)
            if value is None:
                continue
            command = message_type()
            if actuator.write(command, value, self.aggregate.readings):
                publisher.publish(command)

    def _sense(
        self, read: Callable[[Any, Mapping[str, Any]], Mapping[str, Any]], message: Any
    ) -> None:
        """Take the sensors a message of a sensor topic gives."""
        self.aggregate.sense(read(message, self.aggregate.readings))

    def _hear(self, message: Any) -> None:
        """Take a message of the shared topic."""
        self.aggregate.hear(bytes(message.data))


def main(argv: Sequence[str] | None = None) -> None:
    """
    Run the program that the command line names on this robot, until the node is shut down.

    Args:
        argv: The command line, ROS arguments included; ``sys.argv`` if ``None``.
    """
    # pylint: disable=import-error,import-outside-toplevel
    import rclpy
    from rclpy.executors import ExternalShutdownException
    from rclpy.utilities import remove_ros_args

    argv = list(sys.argv if argv is None else argv)
    options = parser().parse_args(remove_ros_args(argv)[1:])
    sensor_topics, actuator_topics = topics_of(options)
    rclpy.init(args=argv)
    host = AggregateRosNode(
        options.program, device_id=options.id, neighbourhood=neighbourhood_of(options),
        sensor_topics=sensor_topics, actuator_topics=actuator_topics,
        sensors=lambda: {"source": host.aggregate.device_id == options.source},
        period=options.period, topic=options.topic, lifetime=options.lifetime,
    )
    try:
        rclpy.spin(host.node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        host.node.destroy_node()
        rclpy.try_shutdown()


def parser() -> argparse.ArgumentParser:
    """The options of the command line, besides the ROS arguments."""
    options = argparse.ArgumentParser(
        prog="python -m phyelds.ros2", description="Run a program on this robot."
    )
    options.add_argument("program", type=_function, help="the program to run, as module:function")
    options.add_argument("--id", help="the id of the robot; its namespace by default")
    options.add_argument("--source", help="the id of the robot that senses source")
    options.add_argument("--neighbourhood", choices=NEIGHBOURHOODS, default="reachable",
                         help="who is a neighbour: whoever is heard, whoever is within --range, or"
                              " whoever tf2 locates")
    options.add_argument("--range", type=float, help="how far a robot reaches, in metres")
    options.add_argument("--frame", help="with tf, the frame of the robot; ID/base_link by default")
    options.add_argument("--fixed-frame", default="map",
                         help="with tf, the frame all the robots are located in (default map)")
    options.add_argument("--measure", action="store_true",
                         help="with reachable, measure the neighbours from their positions")
    options.add_argument("--sense", nargs="*", choices=tuple(SENSES), default=["odom"],
                         help="the topics to sense: odom, a turtlesim pose, a laser scan; or none")
    options.add_argument("--act", nargs="*", choices=ACTS, default=["differential", "label"],
                         help="the outputs to act on: velocity, for a robot that turns or one that"
                              " moves in any direction, and label; or none")
    options.add_argument("--topics", type=_function,
                         help="module:function that returns more SensorTopics and ActuatorTopics")
    options.add_argument("--period", type=float, default=0.1,
                         help="the time between two rounds, in seconds")
    options.add_argument("--max-speed", type=float, default=0.2, help="the top speed, in m/s")
    options.add_argument("--turn-rate", type=float, default=1.0,
                         help="how fast the robot turns, in rad/s per radian off its velocity")
    options.add_argument("--topic", default=TOPIC, help="the topic all the nodes share")
    options.add_argument("--lifetime", type=int, default=2,
                         help="for how many rounds the message of a silent neighbour is kept")
    return options


def neighbourhood_of(
    options: argparse.Namespace,
) -> Neighbourhood | Callable[[Any], Neighbourhood]:
    """
    The neighbourhood strategy the command line asks for.

    Args:
        options: The parsed command line.

    Returns:
        ``WithinRange`` for ``--neighbourhood range``; for ``--neighbourhood tf``, a function
        of the node that builds ``Transforms`` on tf2; ``Reachable`` otherwise.

    Raises:
        ValueError: If ``--neighbourhood range`` comes without ``--range``.
    """
    if options.neighbourhood == "tf":
        def transforms(node: Any) -> Neighbourhood:
            frame = options.frame or f"{options.id or node.get_namespace().strip('/')}/base_link"
            return Transforms(frame, tf_locator(node, options.fixed_frame), radius=options.range)

        return transforms
    if options.neighbourhood == "range":
        if options.range is None:
            raise ValueError("--neighbourhood range needs --range")
        return WithinRange(options.range)
    return Reachable(measure=options.measure)


def topics_of(options: argparse.Namespace) -> tuple[list[SensorTopic], list[ActuatorTopic]]:
    """
    The sensor and actuator topics the command line asks for.

    Args:
        options: The parsed command line.

    Returns:
        Those of ``--sense`` and ``--act``, then those that ``--topics`` returns.

    Raises:
        TypeError: If ``--topics`` returns something that is neither kind of topic.
    """
    sensor_topics = [SENSES[name]() for name in options.sense]
    actuator_topics = [_act(name, options) for name in options.act]
    for extra in options.topics() if options.topics is not None else ():
        if isinstance(extra, SensorTopic):
            sensor_topics.append(extra)
        elif isinstance(extra, ActuatorTopic):
            actuator_topics.append(extra)
        else:
            raise TypeError(f"--topics returned {extra!r}, not a SensorTopic or an ActuatorTopic")
    return sensor_topics, actuator_topics


def _act(name: str, options: argparse.Namespace) -> ActuatorTopic:
    """The actuator topic ``name``, one of ``ACTS``, with the speeds of the command line."""
    if name == "differential":
        return differential_drive(max_speed=options.max_speed, turn_rate=options.turn_rate)
    if name == "holonomic":
        return holonomic_drive(max_speed=options.max_speed)
    return text()


def tf_locator(node: Any, fixed_frame: str = "map") -> Callable[[str], tuple[float, ...] | None]:
    """
    Where frames are in ``fixed_frame``, from the tf2 transforms ``node`` listens to.

    Args:
        node: The ``rclpy`` node that listens.
        fixed_frame: The frame all the robots are located in.

    Returns:
        A function from a frame to its position, ``None`` while tf2 cannot transform it.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformException, TransformListener

    buffer = Buffer()
    node.tf_listener = TransformListener(buffer, node)  # kept with the node, which it feeds

    def locate(frame: str) -> tuple[float, ...] | None:
        try:
            translation = buffer.lookup_transform(fixed_frame, frame, Time()).transform.translation
        except TransformException:
            return None
        return translation.x, translation.y, translation.z

    return locate


def _message_type(name: str) -> type:
    """The class of the message type ``name``, as ``"package/msg/Type"``."""
    # pylint: disable=import-error,import-outside-toplevel
    from rosidl_runtime_py.utilities import get_message

    return get_message(name)


def _function(spec: str) -> Callable[..., Any]:
    """The function that ``spec``, ``module:function``, names."""
    module, _, function = spec.partition(":")
    if not module or not function:
        raise argparse.ArgumentTypeError(f"{spec!r} is not module:function")
    return getattr(importlib.import_module(module), function)

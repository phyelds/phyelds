from types import SimpleNamespace

import pytest

from phyelds.libraries.distances import hops_distance
from phyelds.ros2.host import neighbourhood_of, parser, topics_of
from phyelds.ros2.neighbourhood import Reachable, WithinRange
from phyelds.ros2.topics import command, reading

PROGRAM = "phyelds.libraries.distances:hops_distance"


def test_parser_imports_the_program_the_command_line_names():
    options = parser().parse_args([PROGRAM])

    assert options.program is hops_distance


def test_parser_rejects_a_program_that_is_not_module_and_function():
    with pytest.raises(SystemExit):
        parser().parse_args(["phyelds.libraries.distances"])


def test_neighbourhood_is_reachable_and_measured_when_asked_to():
    strategy = neighbourhood_of(parser().parse_args([PROGRAM, "--measure"]))

    assert isinstance(strategy, Reachable) and strategy.measure


def test_neighbourhood_is_within_the_range_of_the_command_line():
    strategy = neighbourhood_of(parser().parse_args([PROGRAM, "--neighbourhood", "range", "--range", "1.5"]))

    assert isinstance(strategy, WithinRange) and strategy.radius == 1.5


def test_neighbourhood_within_range_needs_a_range():
    with pytest.raises(ValueError, match="--range"):
        neighbourhood_of(parser().parse_args([PROGRAM, "--neighbourhood", "range"]))


def extra_topics():
    return [reading("battery", "battery", "std_msgs/msg/Float32"), command("grip", "gripper", "std_msgs/msg/Bool")]


def not_topics():
    return ["odom"]


def test_topics_sense_the_odometry_and_drive_a_robot_that_turns_by_default():
    sensor_topics, actuator_topics = topics_of(parser().parse_args([PROGRAM]))

    assert [topic.message_type for topic in sensor_topics] == ["nav_msgs/msg/Odometry"]
    assert [(topic.output, topic.topic) for topic in actuator_topics] == [("velocity", "cmd_vel"), ("label", "label")]


def test_topics_can_be_none_or_holonomic_with_the_speed_of_the_command_line():
    options = parser().parse_args([PROGRAM, "--sense", "--act", "holonomic", "--max-speed", "0.5"])
    message = SimpleNamespace(linear=SimpleNamespace(x=0.0, y=0.0), angular=SimpleNamespace(z=0.0))

    sensor_topics, (drive,) = topics_of(options)
    drive.write(message, (3.0, 4.0), {"heading": (1.0, 0.0, 0.0)})

    assert sensor_topics == []
    assert (message.linear.x, message.linear.y) == pytest.approx((0.3, 0.4))


def test_topics_add_those_of_a_function_of_ones_own():
    options = parser().parse_args(
        [PROGRAM, "--sense", "turtlesim", "--act", "--topics", "test_command_line:extra_topics"]
    )

    sensor_topics, actuator_topics = topics_of(options)

    assert [topic.topic for topic in sensor_topics] == ["pose", "battery"]
    assert [topic.output for topic in actuator_topics] == ["grip"]


def test_topics_of_a_function_must_be_topics():
    options = parser().parse_args([PROGRAM, "--topics", "test_command_line:not_topics"])

    with pytest.raises(TypeError, match="odom"):
        topics_of(options)

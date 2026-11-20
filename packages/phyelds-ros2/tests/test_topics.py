import math
from types import SimpleNamespace

import pytest

from phyelds.ros2.topics import (
    command,
    differential_drive,
    holonomic_drive,
    odometry,
    reading,
    text,
    turtle_pose,
)


def _vector(x=0.0, y=0.0, z=0.0):
    return SimpleNamespace(x=x, y=y, z=z)


def _twist():
    return SimpleNamespace(linear=_vector(), angular=_vector())


def test_odometry_senses_the_position_and_heading_of_the_robot():
    angle = math.pi / 2
    orientation = SimpleNamespace(x=0.0, y=0.0, z=math.sin(angle / 2), w=math.cos(angle / 2))
    message = SimpleNamespace(pose=SimpleNamespace(pose=SimpleNamespace(position=_vector(1.0, 2.0, 0.5),
                                                                        orientation=orientation)))

    sensed = odometry().read(message)

    assert sensed["position"] == (1.0, 2.0, 0.5)
    assert sensed["heading"] == pytest.approx((0.0, 1.0, 0.0))


def test_turtle_pose_senses_the_position_and_heading_of_the_turtle():
    sensed = turtle_pose().read(SimpleNamespace(x=1.0, y=2.0, theta=0.0))

    assert sensed == {"position": (1.0, 2.0, 0.0), "heading": (1.0, 0.0, 0.0)}


def test_reading_senses_one_field_of_a_message_under_a_name():
    battery = reading("battery", "battery_state", "sensor_msgs/msg/BatteryState", field="percentage")

    assert battery.read(SimpleNamespace(percentage=0.8)) == {"battery": 0.8}


def test_differential_drive_turns_and_drives_towards_the_velocity():
    message = _twist()

    sent = differential_drive(max_speed=0.5).write(message, (0.2, 0.0), {"heading": (1.0, 0.0, 0.0)})

    assert sent and (message.linear.x, message.angular.z) == (0.2, 0.0)


def test_differential_drive_sends_nothing_before_the_heading_is_known():
    assert not differential_drive().write(_twist(), (0.2, 0.0), {})


def test_holonomic_drive_moves_along_the_velocity_in_the_frame_of_the_robot():
    message = _twist()

    sent = holonomic_drive(max_speed=1.0).write(message, (0.0, 0.3), {"heading": (0.0, 1.0, 0.0)})

    assert sent
    assert (message.linear.x, message.linear.y) == pytest.approx((0.3, 0.0))
    assert message.angular.z == 0.0


def test_holonomic_drive_caps_the_speed():
    message = _twist()

    holonomic_drive(max_speed=0.5).write(message, (3.0, 4.0), {"heading": (1.0, 0.0, 0.0)})

    assert (message.linear.x, message.linear.y) == pytest.approx((0.3, 0.4))


def test_text_publishes_the_output_as_a_string():
    message = SimpleNamespace(data="")

    assert text().write(message, 1.5, {}) and message.data == "1.5"


def test_command_sets_one_field_of_a_message_from_an_output():
    gripper = command("grip", "gripper", "std_msgs/msg/Bool")
    message = SimpleNamespace(data=False)

    assert gripper.write(message, True, {}) and message.data is True
    assert (gripper.output, gripper.topic, gripper.message_type) == ("grip", "gripper", "std_msgs/msg/Bool")

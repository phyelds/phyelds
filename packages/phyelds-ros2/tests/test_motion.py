import math

import pytest

from phyelds.ros2.motion import twist, yaw_of


def test_twist_drives_straight_at_most_at_max_speed_when_facing_the_target():
    linear, angular = twist((3.0, 0.0), yaw=0.0, max_speed=0.5)

    assert (linear, angular) == (0.5, 0.0)


def test_twist_turns_in_place_towards_a_target_behind():
    linear, angular = twist((-1.0, 0.0), yaw=0.0, max_speed=1.0, turn_rate=2.0)

    assert linear == 0.0
    assert abs(angular) == pytest.approx(2.0 * math.pi)


def test_twist_turns_left_towards_a_target_on_the_left():
    linear, angular = twist((0.0, 1.0), yaw=-math.pi / 4, max_speed=1.0)

    assert linear == 0.0
    assert angular == pytest.approx(3 * math.pi / 4)


def test_twist_stops_when_the_target_is_still():
    assert twist((0.0, 0.0), yaw=1.0, max_speed=1.0) == (0.0, 0.0)


@pytest.mark.parametrize("angle", [0.0, 1.0, -2.5, math.pi])
def test_yaw_of_a_rotation_about_the_vertical_axis_is_its_angle(angle):
    quaternion = (0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2))

    assert math.remainder(yaw_of(*quaternion) - angle, math.tau) == pytest.approx(0.0)

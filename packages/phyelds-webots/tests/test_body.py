import math

import pytest

from fakes import LED, Motor, World

from phyelds.libraries.device import led, velocity
from phyelds.webots import Body


def _robot(**devices):
    robot = World(radio_range=0.15).line(1)[0]
    robot.add(**devices)
    return robot


def _wheeled(yaw=0.0, max_velocity=100.0):
    robot = _robot(**{"left wheel motor": Motor(max_velocity), "right wheel motor": Motor(max_velocity)})
    robot.yaw = yaw
    return robot


def _wheels(robot):
    return robot.devices["left wheel motor"].velocity, robot.devices["right wheel motor"].velocity


def test_body_lights_every_led_with_the_colour_the_program_sends():
    robot = _robot(top=LED(), ring=LED())
    body = Body(robot)

    body.act({led.name: (255, 128, 0)})

    assert [robot.devices[name].value for name in ("top", "ring")] == [0xFF8000, 0xFF8000]


def test_body_turns_the_leds_off_when_the_program_sends_no_colour():
    robot = _robot(top=LED())
    body = Body(robot)

    body.act({})

    assert robot.devices["top"].value == 0


def test_body_switches_leds_with_a_colour_list_on_unless_the_colour_is_black():
    robot = _robot(ring=LED())
    body = Body(robot, rgb_leds=False)

    body.act({led.name: (0, 0, 255)})
    on = robot.devices["ring"].value
    body.act({led.name: (0, 0, 0)})

    assert (on, robot.devices["ring"].value) == (1, 0)


def test_body_drives_both_wheels_along_a_velocity_it_already_faces():
    robot = _wheeled()
    body = Body(robot, wheel_radius=0.02)

    body.act({velocity.name: (0.05, 0.0)})

    assert _wheels(robot) == (2.5, 2.5)
    assert robot.devices["left wheel motor"].position == math.inf


def test_body_turns_on_the_spot_towards_a_velocity_at_its_side():
    robot = _wheeled(yaw=math.pi / 2)
    body = Body(robot, wheel_radius=0.02)

    body.act({velocity.name: (0.05, 0.0)})

    left, right = _wheels(robot)
    assert left == pytest.approx(0.05 * math.pi / 2 / 0.02)
    assert right == pytest.approx(-left)


def test_body_stands_still_when_the_program_sends_no_velocity():
    robot = _wheeled()
    body = Body(robot, wheel_radius=0.02)

    body.act({})

    assert _wheels(robot) == (0.0, 0.0)


def test_body_rejects_wheels_without_their_radius():
    with pytest.raises(ValueError, match="wheel_radius"):
        Body(_wheeled())


def test_body_rejects_wheels_without_an_inertial_unit_to_steer_by():
    robot = _wheeled()
    del robot.devices["inertial unit"]

    with pytest.raises(ValueError, match="InertialUnit"):
        Body(robot, wheel_radius=0.02)

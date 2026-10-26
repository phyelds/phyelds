import math

import pytest

from fakes import LED, DistanceSensor, Motor, World

from phyelds.libraries.device import led, obstacle, velocity
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


def test_body_caps_the_velocity_at_its_max_speed():
    robot = _wheeled()
    body = Body(robot, wheel_radius=0.02, max_speed=0.1)

    body.act({velocity.name: (1.0, 0.0)})

    assert _wheels(robot) == (5.0, 5.0)


def test_body_slows_both_wheels_alike_to_keep_within_what_the_motors_reach():
    robot = _wheeled(yaw=math.pi / 4, max_velocity=3.0)
    body = Body(robot, wheel_radius=0.02)

    body.act({velocity.name: (0.1, 0.0)})

    left, right = _wheels(robot)
    free_left, free_right = _free_wheels(yaw=math.pi / 4, target=(0.1, 0.0))
    assert max(abs(left), abs(right)) == pytest.approx(3.0)
    assert left / right == pytest.approx(free_left / free_right)


def _free_wheels(yaw, target):
    """The wheel speeds of a robot whose motors have no limit in reach."""
    robot = _wheeled(yaw=yaw)
    Body(robot, wheel_radius=0.02).act({velocity.name: target})
    return _wheels(robot)


def test_body_senses_away_from_what_its_distance_sensors_see_in_the_world_frame():
    robot = _robot(right=DistanceSensor(yaw=-math.pi / 2, value=4095.0), front=DistanceSensor(yaw=0.0))
    robot.yaw = math.pi / 2
    body = Body(robot)

    away = body.sense()[obstacle.name]

    assert away == pytest.approx((-1.0, 0.0, 0.0))


def test_body_senses_no_obstacle_without_distance_sensors():
    assert Body(_robot()).sense()[obstacle.name] is None


def test_body_measures_closeness_by_distance_through_the_lookup_table():
    # The e-puck's: values fall fast with distance, 234.93 is 3 cm of 7.
    table = (0.0, 4095.0, 0.0, 0.01, 1465.73, 0.0, 0.03, 234.93, 0.0, 0.07, 67.19, 0.0)
    body = Body(_robot(front=DistanceSensor(yaw=0.0, value=234.93, table=table)))

    away = body.sense()[obstacle.name]

    assert away == pytest.approx((-(1 - 0.03 / 0.07), 0.0, 0.0))


def test_body_drives_wheels_of_the_names_it_is_given():
    robot = _robot(**{"motor.left": Motor(), "motor.right": Motor()})
    body = Body(robot, wheel_radius=0.02, wheels=("motor.left", "motor.right"))

    body.act({velocity.name: (0.05, 0.0)})

    assert (robot.devices["motor.left"].velocity, robot.devices["motor.right"].velocity) == (2.5, 2.5)


def test_body_rejects_a_robot_with_only_one_of_its_wheels():
    robot = _robot(**{"left wheel motor": Motor()})

    with pytest.raises(ValueError, match="right wheel motor"):
        Body(robot, wheel_radius=0.02)


def test_body_follows_a_distance_sensor_inside_a_solid_of_its_own_name():
    # As on the Elisa-3, whose sensors are turned once by their solid, and back by themselves.
    body = Body(_robot(front=DistanceSensor(yaw=0.0, value=4095.0, wrapped=True)))

    away = body.sense()[obstacle.name]

    assert away == pytest.approx((-1.0, 0.0, 0.0))

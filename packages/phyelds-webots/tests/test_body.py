from fakes import LED, World

from phyelds.libraries.device import led
from phyelds.webots import Body


def _robot(**devices):
    robot = World(radio_range=0.15).line(1)[0]
    robot.devices.update(devices)
    return robot


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

"""ARGoS experiments that put each robot ARGoS simulates under the phyelds controller."""
from dataclasses import dataclass

_RAB = '<range_and_bearing implementation="default" />'
_RAB_SENSOR = '<range_and_bearing implementation="medium" medium="rab" />'
_RAB_MEDIA = '<range_and_bearing id="rab" check_occlusions="false" /><led id="leds" />'
_RADIOS = '<simple_radios implementation="default" />'
_POSITIONING = '<positioning implementation="default" />'
_FLOOR = '<dynamics3d id="dyn3d" iterations="20"><gravity g="9.8" /><floor /></dynamics3d>'


@dataclass(frozen=True)
class Robot:
    """A robot type, with the devices and the world it needs.

    ``wall`` is how far from the robot a wall is seen by its proximity sensors, if any.
    """

    tag: str
    attributes: str
    actuators: str
    sensors: str
    engine: str
    media: str
    spacing: float = 0.5
    wall: float | None = None
    mobile: bool = True
    body: str = ""


ROBOTS = {
    "foot-bot": Robot(
        "foot-bot", 'rab_range="0.65" rab_data_size="4096"',
        f'<differential_steering implementation="default" /><leds implementation="default" medium="leds" />{_RAB}',
        f'{_RAB_SENSOR}{_POSITIONING}<footbot_proximity implementation="default" />',
        '<dynamics2d id="dyn2d" />', _RAB_MEDIA, wall=0.13,
    ),
    "e-puck": Robot(
        "e-puck", 'rab_range="0.65" rab_data_size="4096"',
        f'<differential_steering implementation="default" /><leds implementation="default" medium="leds" />{_RAB}',
        f'{_RAB_SENSOR}{_POSITIONING}<epuck_proximity implementation="default" />',
        '<dynamics2d id="dyn2d" />', _RAB_MEDIA, wall=0.08,
    ),
    "eye-bot": Robot(
        "eye-bot", 'rab_range="0.65" rab_data_size="4096"',
        f'<quadrotor_speed implementation="default" /><leds implementation="default" medium="leds" />{_RAB}',
        f'{_RAB_SENSOR}{_POSITIONING}<eyebot_proximity implementation="default" />',
        # pointmass3d moves quadrotors by its physics tick once per tick: one iteration each.
        '<pointmass3d id="pm3d" iterations="1" />', _RAB_MEDIA, spacing=0.6, wall=0.5,
    ),
    "spiri": Robot(
        "spiri", 'rab_range="0.65" rab_data_size="4096"',
        f'<quadrotor_speed implementation="default" />{_RAB}', f'{_RAB_SENSOR}{_POSITIONING}',
        '<pointmass3d id="pm3d" />', _RAB_MEDIA,
    ),
    "pi-puck": Robot(
        "pipuck", 'wifi_medium="wifi" led_medium="directional_leds"',
        f'<pipuck_differential_drive implementation="default" /><pipuck_leds implementation="default" />{_RADIOS}',
        f'{_RADIOS}{_POSITIONING}<pipuck_rangefinders implementation="default" />',
        # Under dynamics3d the Pi-Puck barely turns in place.
        '<dynamics2d id="dyn2d" />', '<simple_radio id="wifi" /><directional_led id="directional_leds" />',
        wall=0.09,
    ),
    "builderbot": Robot(
        "builderbot", "",
        f'<builderbot_differential_drive implementation="default" /><builderbot_leds implementation="default" />'
        f'{_RADIOS}',
        f'{_RADIOS}{_POSITIONING}<builderbot_rangefinders implementation="default" />',
        _FLOOR, '<simple_radio id="wifi" /><simple_radio id="nfc" /><tag id="tags" />'
        '<directional_led id="directional_leds" />', wall=0.11,
    ),
    "drone": Robot(
        "drone", 'wifi_medium="wifi" led_medium="directional_leds"',
        f'<drone_flight_system implementation="default" /><drone_leds implementation="default" />{_RADIOS}',
        f'<drone_flight_system implementation="default" />{_RADIOS}{_POSITIONING}',
        '<pointmass3d id="pm3d" />', '<simple_radio id="wifi" /><directional_led id="directional_leds" />',
    ),
    "block": Robot(
        "block", 'movable="false"', f'<directional_leds implementation="default" />{_RADIOS}',
        f'{_RADIOS}{_POSITIONING}', _FLOOR,
        '<simple_radio id="nfc" /><tag id="tags" /><directional_led id="directional_leds" />',
        spacing=0.055, mobile=False,
    ),
    "prototype": Robot(
        "prototype", 'movable="false"', f'<leds implementation="default" medium="leds" />{_RADIOS}',
        f'{_RADIOS}{_POSITIONING}', _FLOOR, '<simple_radio id="radio" /><led id="leds" />',
        mobile=False, body=(
            '<links ref="base"><link id="base" geometry="box" size="0.1,0.1,0.05" mass="0.1"'
            ' position="0,0,0" orientation="0,0,0" /></links><devices>'
            '<simple_radios><simple_radio id="radio" anchor="base" position="0,0,0.05" medium="radio" range="0.6" />'
            '</simple_radios><leds medium="leds"><led anchor="base" offset="0,0,0.05" color="black" /></leds>'
            '</devices>'
        ),
    ),
}


def experiment(robot: Robot, plugin: str, program: str, *, count: int = 5, yaw: float = 0,
               params: str = "", seconds: float = 3, arena: str = "") -> str:
    """An experiment with a line of ``count`` robots along x, running ``program``."""
    robots = "".join(
        f'<{robot.tag} id="r{index}" {robot.attributes}><body position="{index * robot.spacing},0,0"'
        f' orientation="{yaw},0,0" /><controller config="phyelds" />{robot.body}</{robot.tag}>'
        for index in range(count)
    )
    return f"""<?xml version="1.0" ?>
<argos-configuration>
  <framework>
    <system threads="0" />
    <experiment length="{seconds}" ticks_per_second="10" random_seed="1" />
  </framework>
  <controllers>
    <phyelds_controller id="phyelds" library="{plugin}">
      <actuators>{robot.actuators}</actuators>
      <sensors>{robot.sensors}</sensors>
      <params program="{program}" source="0" {params} />
    </phyelds_controller>
  </controllers>
  <arena size="8,8,3" center="0,0,1">{robots}{arena}</arena>
  <physics_engines>{robot.engine}</physics_engines>
  <media>{robot.media}</media>
</argos-configuration>
"""

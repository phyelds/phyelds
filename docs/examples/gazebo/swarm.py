"""
Robots of Gazebo that measure how far the source robot is, gather around it, and keep off walls.

``world`` writes the SDF of the world: differential-drive robots, each with a lidar, whose
odometry, velocity and scan are on ``/NAME/odom``, ``/NAME/cmd_vel`` and ``/NAME/scan``.
"""
from collections.abc import Mapping

from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector, sink_at, stand_still
from phyelds.libraries.device import label, obstacle, source, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

NEAR = 0.8
"""How close to the source a robot stops, in metres."""

SPEED = 0.3
"""How fast a robot heads to the source, in m/s."""

AVOID = 0.6
"""How fast a robot moves away from a wall it touches, in m/s."""

ROBOTS = {
    "robot1": (0.0, 0.0),  # the source
    "robot2": (-1.5, 0.0),
    "robot3": (1.5, 0.0),
    "robot4": (0.0, -1.5),
    "robot5": (-1.5, -1.5),  # beyond the range of robot1: it is reached through robot2 or robot4
}
"""Where each robot starts, in metres."""

WALL = ((0.0, 2.0), (4.0, 0.1))
"""The centre and the size of a wall, in metres, north of the robots."""

_PLANE = "<plane><normal>0 0 1</normal><size>20 20</size></plane>"


# --8<-- [start:program]
@aggregate
def main() -> float:
    """Show the distance to the source, head to it along the network until near, keep off walls."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(f"{distance:.2f}m")
    # Every robot computes the way to the source, near or not, so that all of them align.
    to_source = sink_at(source.sense())
    towards = to_source * SPEED if distance > NEAR else stand_still()
    away = obstacle.sense()
    velocity.send(towards if away is None else towards + Vector(*away) * AVOID)
    return distance
# --8<-- [end:program]


def bridge(robots: Mapping[str, tuple[float, float]] | None = None) -> list[str]:
    """
    The arguments of ``ros_gz_bridge parameter_bridge`` that bring the topics of ``robots``,
    and the clock of the simulation, to ROS 2.

    Args:
        robots: The robots, by name; ``ROBOTS`` if ``None``.

    Returns:
        One argument per topic.
    """
    robots = ROBOTS if robots is None else robots
    topics = ["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"]
    for name in robots:
        topics += [
            f"/{name}/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            f"/{name}/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            f"/{name}/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
        ]
    return topics


def world(robots: Mapping[str, tuple[float, float]] | None = None, *, wall: bool = True) -> str:
    """
    The SDF of a world with ``robots``, by name and start position, and a wall if ``wall``.

    Args:
        robots: The robots, by name, with where they start; ``ROBOTS`` if ``None``.
        wall: Whether to build the wall of ``WALL``.

    Returns:
        The SDF, for ``gz sim``.
    """
    robots = ROBOTS if robots is None else robots
    models = "".join(_robot(name, x, y) for name, (x, y) in robots.items())
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <world name="swarm">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <light type="directional" name="sun">
      <pose>0 0 10 0 0 0</pose>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <model name="ground">
      <static>true</static>
      <link name="link">
        <collision name="collision"><geometry>{_PLANE}</geometry></collision>
        <visual name="visual"><geometry>{_PLANE}</geometry></visual>
      </link>
    </model>
    {_wall() if wall else ""}
    {models}
  </world>
</sdf>
"""


def _wall() -> str:
    """The SDF of the wall of ``WALL``."""
    (x, y), (length, width) = WALL
    box = f"<box><size>{length} {width} 0.5</size></box>"
    return f"""<model name="wall">
      <static>true</static>
      <pose>{x} {y} 0.25 0 0 0</pose>
      <link name="link">
        <collision name="collision"><geometry>{box}</geometry></collision>
        <visual name="visual"><geometry>{box}</geometry></visual>
      </link>
    </model>"""


def _robot(name: str, x: float, y: float) -> str:
    """The SDF of a differential-drive robot with a lidar, named ``name``, at ``(x, y)``."""
    return f"""
    <model name="{name}">
      <pose>{x} {y} 0 0 0 0</pose>
      <link name="chassis">
        <pose>0 0 0.1 0 0 0</pose>
        <inertial><mass>1.0</mass><inertia><ixx>0.004</ixx><iyy>0.008</iyy><izz>0.01</izz></inertia></inertial>
        <collision name="collision"><geometry><box><size>0.3 0.2 0.08</size></box></geometry></collision>
        <visual name="visual"><geometry><box><size>0.3 0.2 0.08</size></box></geometry></visual>
        <sensor name="lidar" type="gpu_lidar">
          <pose>0 0 0.08 0 0 0</pose>
          <topic>/{name}/scan</topic>
          <update_rate>10</update_rate>
          <lidar>
            <scan>
              <horizontal>
                <samples>72</samples><min_angle>-3.14159</min_angle><max_angle>3.14159</max_angle>
              </horizontal>
            </scan>
            <range><min>0.2</min><max>2.0</max></range>
          </lidar>
          <always_on>true</always_on>
        </sensor>
      </link>
      {_wheel("left", 0.12)}
      {_wheel("right", -0.12)}
      <link name="caster">
        <pose>-0.1 0 0.05 0 0 0</pose>
        <inertial><mass>0.05</mass><inertia><ixx>0.00005</ixx><iyy>0.00005</iyy><izz>0.00005</izz></inertia></inertial>
        <collision name="collision">
          <geometry><sphere><radius>0.05</radius></sphere></geometry>
          <surface><friction><ode><mu>0</mu><mu2>0</mu2></ode></friction></surface>
        </collision>
      </link>
      <joint name="caster_joint" type="fixed"><parent>chassis</parent><child>caster</child></joint>
      <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
        <left_joint>left_wheel_joint</left_joint>
        <right_joint>right_wheel_joint</right_joint>
        <wheel_separation>0.24</wheel_separation>
        <wheel_radius>0.05</wheel_radius>
        <topic>/{name}/cmd_vel</topic>
      </plugin>
      <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">
        <odom_frame>world</odom_frame>
        <robot_base_frame>{name}/base_link</robot_base_frame>
        <odom_topic>/{name}/odom</odom_topic>
        <odom_publish_frequency>20</odom_publish_frequency>
      </plugin>
    </model>"""


def _wheel(side: str, y: float) -> str:
    """The SDF of the wheel on ``side``, at ``y`` from the centre, and of its joint."""
    cylinder = "<cylinder><radius>0.05</radius><length>0.03</length></cylinder>"
    return f"""<link name="{side}_wheel">
        <pose>0.05 {y} 0.05 -1.5708 0 0</pose>
        <inertial><mass>0.2</mass><inertia><ixx>0.0002</ixx><iyy>0.0002</iyy><izz>0.0003</izz></inertia></inertial>
        <collision name="collision"><geometry>{cylinder}</geometry></collision>
        <visual name="visual"><geometry>{cylinder}</geometry></visual>
      </link>
      <joint name="{side}_wheel_joint" type="revolute">
        <parent>chassis</parent>
        <child>{side}_wheel</child>
        <axis><xyz>0 0 1</xyz></axis>
      </joint>"""

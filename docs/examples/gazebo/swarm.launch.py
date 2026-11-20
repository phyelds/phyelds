"""
Five robots in Gazebo, each with its phyelds node: ``ros2 launch swarm.launch.py``.

Run it from this directory, so that the nodes import ``swarm``; ``gui:=false`` runs Gazebo
without its window. The robots hear each other within ``RANGE`` metres, measure how far
``robot1`` is along the network, gather around it, and keep off the wall.
"""
# pylint: disable=import-error
import sys
import tempfile
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

sys.path.insert(0, str(Path(__file__).resolve().parent))

import swarm  # noqa: E402  pylint: disable=wrong-import-position

RANGE = 2.0
"""How far a robot hears another, in metres."""


def generate_launch_description() -> LaunchDescription:
    """Gazebo with the world of ``swarm``, the bridge of its topics, and a node per robot."""
    here = Path(__file__).resolve().parent
    with tempfile.NamedTemporaryFile("w", suffix=".sdf", delete=False) as world:
        world.write(swarm.world())
    gui = LaunchConfiguration("gui")
    actions = [
        DeclareLaunchArgument("gui", default_value="true", description="show the window of Gazebo"),
        ExecuteProcess(cmd=["gz", "sim", "-r", world.name], condition=IfCondition(gui)),
        ExecuteProcess(cmd=["gz", "sim", "-r", "-s", "--headless-rendering", world.name],
                       condition=UnlessCondition(gui)),
        Node(package="ros_gz_bridge", executable="parameter_bridge", arguments=swarm.bridge()),
    ]
    # --8<-- [start:nodes]
    for name in swarm.ROBOTS:
        actions.append(ExecuteProcess(
            cmd=[
                sys.executable, "-m", "phyelds.ros2", "swarm:main", "--sense", "odom", "scan",
                "--neighbourhood", "range", "--range", str(RANGE), "--source", "robot1",
                "--max-speed", "0.3",
                "--ros-args", "-r", f"__ns:=/{name}", "-p", "use_sim_time:=true",
            ],
            cwd=str(here), output="screen",
        ))
    # --8<-- [end:nodes]
    return LaunchDescription(actions)

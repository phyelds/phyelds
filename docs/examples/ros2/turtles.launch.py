"""
Five turtles of turtlesim, each with its phyelds node: ``ros2 launch turtles.launch.py``.

Run it from this directory, so that the nodes import ``turtles``. The turtles hear each other
within ``RANGE`` metres, measure how far ``turtle1`` is along the network, and gather around it.
"""
import sys
from pathlib import Path

# pylint: disable=import-error
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

RANGE = 3.5
"""How far a turtle hears another, in metres."""

# --8<-- [start:turtles]
TURTLES = {
    "turtle1": (5.5, 5.5),  # the source, where turtlesim puts its first turtle
    "turtle2": (2.5, 5.5),
    "turtle3": (8.5, 5.5),
    "turtle4": (5.5, 2.5),
    "turtle5": (2.5, 2.5),  # beyond the range of turtle1: it is reached through turtle2 or turtle4
}
# --8<-- [end:turtles]


def generate_launch_description() -> LaunchDescription:
    """The turtlesim window, the turtles it spawns, and a phyelds node for each turtle."""
    here = Path(__file__).resolve().parent
    actions = [Node(package="turtlesim", executable="turtlesim_node")]
    for name, (x, y) in list(TURTLES.items())[1:]:
        request = f"{{x: {x}, y: {y}, theta: 0.0, name: '{name}'}}"
        spawn = ["ros2", "service", "call", "/spawn", "turtlesim/srv/Spawn", request]
        actions.append(ExecuteProcess(cmd=spawn))
    for name in TURTLES:
        actions.append(ExecuteProcess(
            cmd=[
                sys.executable, "-m", "phyelds.ros2", "turtles:main", "--sense", "turtlesim",
                "--neighbourhood", "range", "--range", str(RANGE), "--source", "turtle1",
                "--max-speed", "1.0", "--ros-args", "-r", f"__ns:=/{name}",
            ],
            cwd=str(here), output="screen",
        ))
    return LaunchDescription(actions)

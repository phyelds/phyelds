import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from phyelds.ros2 import AggregateNode, WithinRange
from phyelds.ros2.topics import differential_drive, turtle_pose

sys.path.insert(0, str(Path(__file__).parents[3] / "docs" / "examples" / "ros2"))

import turtles  # noqa: E402  pylint: disable=wrong-import-position,import-error

POSITIONS = {"turtle1": (1.0, 1.0), "turtle2": (3.0, 1.0), "turtle3": (5.0, 1.0)}


def _turtles():
    nodes = []
    for name, (x, y) in POSITIONS.items():
        node = AggregateNode(
            name, turtles.main, neighbourhood=WithinRange(2.5), sensors=lambda name=name: {"source": name == "turtle1"}
        )
        node.sense(turtle_pose().read(SimpleNamespace(x=x, y=y, theta=math.pi)))
        nodes.append(node)
    return nodes


def _run(nodes, rounds):
    for time in range(rounds):
        sent = [node.run_round(float(time)) for node in nodes]
        for node in nodes:
            for data in sent:
                node.hear(data)


def test_turtles_measure_the_distance_to_the_source_along_the_network():
    nodes = _turtles()

    _run(nodes, rounds=5)

    assert [node.result for node in nodes] == pytest.approx([0.0, 2.0, 4.0])
    assert [node.outputs["label"] for node in nodes] == ["0.0m", "2.0m", "4.0m"]


def test_turtles_far_from_the_source_head_to_it_and_the_near_ones_stand_still():
    nodes = _turtles()

    _run(nodes, rounds=5)

    drive, twists = differential_drive(max_speed=1.0), []
    for node in nodes:
        message = SimpleNamespace(linear=SimpleNamespace(x=0.0), angular=SimpleNamespace(z=0.0))
        drive.write(message, node.outputs["velocity"], node.readings)
        twists.append((message.linear.x, message.angular.z))
    assert twists[0] == (0.0, 0.0)
    assert twists[1] == pytest.approx((1.0, 0.0)) and twists[2] == pytest.approx((1.0, 0.0))


def test_turtles_launch_spawns_every_turtle_but_the_first_and_runs_a_node_for_each():
    pytest.importorskip("launch_ros")
    import importlib.util  # pylint: disable=import-outside-toplevel

    path = Path(__file__).parents[3] / "docs" / "examples" / "ros2" / "turtles.launch.py"
    spec = importlib.util.spec_from_file_location("turtles_launch", path)
    launch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launch)

    commands = [
        " ".join(getattr(part, "text", "") for parts in action.cmd for part in parts)
        for action in launch.generate_launch_description().entities if hasattr(action, "cmd")
    ]
    nodes = [command for command in commands if "phyelds.ros2" in command]
    spawned = [command for command in commands if "/spawn" in command]

    assert len(nodes) == len(launch.TURTLES)
    assert len(spawned) == len(launch.TURTLES) - 1

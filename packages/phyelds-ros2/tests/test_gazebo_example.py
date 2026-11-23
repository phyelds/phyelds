import math
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from types import SimpleNamespace

import pytest

from phyelds.ros2 import AggregateNode, WithinRange
from phyelds.ros2.topics import laser_obstacle

sys.path.insert(0, str(Path(__file__).parents[3] / "docs" / "examples" / "gazebo"))

import swarm  # noqa: E402  pylint: disable=wrong-import-position,import-error


def _robots(positions, scans=None):
    nodes = []
    for name, (x, y) in positions.items():
        node = AggregateNode(
            name, swarm.main, neighbourhood=WithinRange(2.0), sensors=lambda name=name: {"source": name == "robot1"}
        )
        node.sense({"position": (x, y, 0.0), "heading": (1.0, 0.0, 0.0)})
        if scans and name in scans:
            node.sense(laser_obstacle().read(scans[name], node.readings))
        nodes.append(node)
    return nodes


def _run(nodes, rounds=8):
    for time in range(rounds):
        sent = [node.run_round(float(time)) for node in nodes]
        for node in nodes:
            for data in sent:
                node.hear(data)


def test_world_has_every_robot_with_its_drive_odometry_and_lidar_on_its_own_topics():
    root = ElementTree.fromstring(swarm.world())

    robots = {model.get("name"): model for model in root.iter("model") if model.get("name") in swarm.ROBOTS}

    assert set(robots) == set(swarm.ROBOTS)
    for name, model in robots.items():
        topics = {element.text for element in model.iter() if element.tag in ("topic", "odom_topic")}
        assert topics == {f"/{name}/cmd_vel", f"/{name}/odom", f"/{name}/scan"}


def test_bridge_brings_the_clock_and_the_topics_of_every_robot():
    topics = swarm.bridge()

    assert topics[0].startswith("/clock@") and len(topics) == 1 + 3 * len(swarm.ROBOTS)
    assert "/robot2/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" in topics


def test_robots_measure_the_source_along_the_network_and_head_to_it():
    nodes = _robots(swarm.ROBOTS)

    _run(nodes)

    distances = {node.device_id: node.result for node in nodes}
    assert distances["robot1"] == 0.0 and distances["robot2"] == pytest.approx(1.5)
    assert distances["robot5"] == pytest.approx(3.0)  # through robot2 or robot4
    assert nodes[0].outputs["velocity"].length() == 0.0
    x, y, _ = nodes[1].outputs["velocity"]
    assert (x, y) == pytest.approx((swarm.SPEED, 0.0))


def test_robots_keep_off_a_wall_they_see():
    ahead = SimpleNamespace(ranges=[0.2, 2.5, 2.5, 2.5], angle_min=0.0, angle_increment=math.pi / 2,
                            range_min=0.2, range_max=2.0)
    nodes = _robots({"robot1": (0.0, 0.0), "robot2": (0.5, 0.0)}, scans={"robot2": ahead})

    _run(nodes)

    x, _, _ = nodes[1].outputs["velocity"]
    assert x == pytest.approx(-swarm.AVOID)

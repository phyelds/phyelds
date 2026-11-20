import os
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from phyelds.ros2 import AggregateRosNode, WithinRange
from phyelds.ros2.topics import differential_drive, laser_obstacle, odometry

rclpy = pytest.importorskip("rclpy")
pytestmark = pytest.mark.skipif(shutil.which("gz") is None, reason="Gazebo (gz) is not on the PATH")

# pylint: disable=wrong-import-position,wrong-import-order,import-error
from rclpy.executors import SingleThreadedExecutor  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[3] / "docs" / "examples" / "gazebo"))

import swarm  # noqa: E402

# robot3 faces the wall, whose face is 1.95 m north, from 0.4 m.
ROBOTS = {"robot1": (0.0, 0.0), "robot2": (1.5, 0.0), "robot3": (0.0, 1.55)}
SPINS = 30_000


@pytest.fixture(name="gazebo")
def _gazebo(tmp_path):
    world = tmp_path / "world.sdf"
    world.write_text(swarm.world(ROBOTS))
    processes = [
        subprocess.Popen(["gz", "sim", "-r", "-s", "--headless-rendering", str(world)], start_new_session=True),
        subprocess.Popen(["ros2", "run", "ros_gz_bridge", "parameter_bridge", *swarm.bridge(ROBOTS)],
                         start_new_session=True),
    ]
    rclpy.init()
    executor = SingleThreadedExecutor()
    yield executor
    executor.shutdown()
    rclpy.try_shutdown()
    for process in processes:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=30)


def test_robots_in_gazebo_gather_around_the_source_and_sense_the_wall(gazebo):
    topic = f"/phyelds/test_{uuid.uuid4().hex}"
    hosts = {
        name: AggregateRosNode(
            swarm.main, namespace=f"/{name}", neighbourhood=WithinRange(2.0), period=0.1, topic=topic,
            sensor_topics=[odometry(), laser_obstacle()],
            actuator_topics=[differential_drive(max_speed=0.3)],
            sensors=lambda name=name: {"source": name == "robot1"},
        )
        for name in ROBOTS
    }
    for host in hosts.values():
        gazebo.add_node(host.node)

    def readings(name):
        return hosts[name].aggregate.readings

    def done():
        position, away = readings("robot2").get("position"), readings("robot3").get("obstacle")
        return position is not None and position[0] < 1.2 and away is not None and away != (0.0, 0.0, 0.0)

    for _ in range(SPINS):
        if done():
            break
        gazebo.spin_once(timeout_sec=0.01)

    assert all(readings(name).get("position") is not None for name in ROBOTS), "no odometry from Gazebo"
    assert readings("robot2")["position"][0] < 1.2, "robot2 did not head to the source"
    away = readings("robot3").get("obstacle")
    assert away is not None and away[1] < 0.0, f"robot3 did not sense the wall: {away}"

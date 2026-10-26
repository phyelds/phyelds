"""Every wheeled robot of Webots runs the same programs under the phyelds controller, in Webots."""
import ast

import pytest
from robots import ROBOTS
from session import WEBOTS, run_world

DRIVEN = 10.0  # seconds of simulated time the mover drives north
pytestmark = pytest.mark.skipif(WEBOTS is None, reason="webots is not on the PATH")


@pytest.fixture(name="world", scope="module", params=list(ROBOTS))
def _world(request, tmp_path_factory):
    """The robot, and the last label of each of its robots, once the mover has driven a while."""
    robot = ROBOTS[request.param]

    def done(labels):
        return {"g0", "g1", "g2", "watcher"} <= labels.keys() and float(labels.get("mover", "0").split()[0]) >= DRIVEN

    labels, output = run_world(robot.write_world(tmp_path_factory.mktemp(request.param)), done, timeout=300)
    assert done(labels), output
    return robot, labels


def test_robots_measure_their_distance_from_the_source_over_the_radio(world):
    robot, labels = world

    distances = [float(labels[name]) for name in ("g0", "g1", "g2")]

    assert distances == pytest.approx([0.0, robot.spacing, 2 * robot.spacing], abs=0.002)


def test_robots_drive_along_a_velocity_in_the_frame_of_the_world(world):
    _, labels = world

    _, x, y = map(float, labels["mover"].split())

    north = y - 4.0  # the mover starts at y = 4, facing east, and turns as it drives
    assert north > 0.2
    assert abs(x) < north


def test_robots_sense_away_from_a_wall_in_front_of_them(world):
    robot, labels = world

    away = ast.literal_eval(labels["watcher"].removeprefix("obstacle="))

    if robot.wall is None:
        pytest.skip("the robot sees no walls")
    assert away[0] < -0.1
    assert abs(away[1]) < abs(away[0])

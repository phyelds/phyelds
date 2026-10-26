import sys
import types

import pytest
from fakes import LED, DistanceSensor, Emitter, Motor, Receiver, World

from phyelds.webots import main


@pytest.fixture(name="robot")
def _robot(monkeypatch):
    """A robot alone, in a world that ends after three steps, that ``controller.Robot()`` gives."""
    robot = World(radio_range=0.15, end=0.096).line(1)[0]
    monkeypatch.setitem(sys.modules, "controller", types.SimpleNamespace(Robot=lambda: robot))
    return robot


def _main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["phyelds", *args])
    main()


def test_main_runs_the_program_its_arguments_name_and_logs_its_label_at_the_end(robot, monkeypatch, capsys):
    _main(monkeypatch, "programs:says_if_source", "--source", robot.name)

    assert capsys.readouterr().out.splitlines() == [f"{robot.name} final: source=True"]


def test_main_logs_the_label_at_every_round_with_trace(robot, monkeypatch, capsys):
    _main(monkeypatch, "programs:says_if_source", "--trace")

    assert capsys.readouterr().out.splitlines() == [f"{robot.name} round: source=False"] * 3 + [
        f"{robot.name} final: source=False"
    ]


def test_main_runs_a_round_every_few_steps_of_the_world(robot, monkeypatch):
    _main(monkeypatch, "programs:says_if_source", "--steps-per-round", "4")

    assert set(robot.durations) == {4 * 32}


def test_main_senses_the_heading_from_an_inertial_unit_of_the_robot(robot, monkeypatch, capsys):
    robot.yaw = 0.0

    _main(monkeypatch, "programs:says_where")

    assert "heading=(1.0, 0.0, 0.0)" in capsys.readouterr().out


def test_main_senses_the_position_only_with_gps(robot, monkeypatch, capsys):
    robot.position = [1.0, 2.0, 0.0]

    _main(monkeypatch, "programs:says_where")
    robot.world.time = 0.0
    _main(monkeypatch, "programs:says_where", "--gps")

    without, with_gps = capsys.readouterr().out.splitlines()
    assert "position=None" in without
    assert "position=(1.0, 2.0, 0.0)" in with_gps


def test_main_drives_the_wheels_with_their_radius_and_the_max_speed(robot, monkeypatch):
    robot.add(**{"left wheel motor": Motor(), "right wheel motor": Motor()})

    _main(monkeypatch, "programs:drives_blue", "--wheel-radius", "0.02", "--max-speed", "0.05")

    assert robot.devices["left wheel motor"].velocity == robot.devices["right wheel motor"].velocity == 2.5


def test_main_switches_leds_with_a_colour_list_on_or_off(robot, monkeypatch):
    robot.add(ring=LED())

    _main(monkeypatch, "programs:drives_blue", "--on-off-leds")

    assert robot.devices["ring"].value == 1


def test_main_sends_compact_paths_unless_asked_for_debug_ones(robot, monkeypatch):
    _main(monkeypatch, "programs:counts_neighbors")
    compact = robot.world.sent[-1][1]
    robot.world.time = 0.0
    _main(monkeypatch, "programs:counts_neighbors", "--paths", "debug")
    debug = robot.world.sent[-1][1]

    assert b"counts_neighbors" not in compact
    assert b"counts_neighbors" in debug


def test_main_rejects_a_program_that_is_not_module_colon_function(robot, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        _main(monkeypatch, "programs")

    assert "module:function" in capsys.readouterr().err
    assert not robot.durations


def test_main_rejects_a_robot_without_a_radio(robot, monkeypatch):
    del robot.devices["emitter"]

    with pytest.raises(ValueError, match="Emitter"):
        _main(monkeypatch, "programs:says_if_source")


def test_main_rejects_gps_on_a_robot_without_one(robot, monkeypatch):
    del robot.devices["gps"]

    with pytest.raises(ValueError, match="GPS"):
        _main(monkeypatch, "programs:says_where", "--gps")


def test_main_senses_away_from_what_the_distance_sensors_see(robot, monkeypatch, capsys):
    robot.add(front=DistanceSensor(yaw=0.0, value=4095.0))

    _main(monkeypatch, "programs:says_obstacle")

    assert "obstacle=(-1.0, 0.0, 0.0)" in capsys.readouterr().out


def test_main_talks_over_the_radio_its_arguments_name(robot, monkeypatch):
    # Stock robots come with a radio of infinite range: the world adds one with a range.
    robot.add(radio_tx=Emitter(robot.world, robot), radio_rx=Receiver())

    _main(monkeypatch, "programs:counts_neighbors", "--emitter", "radio_tx", "--receiver", "radio_rx")

    assert robot.devices["radio_tx"].last is not None and robot.devices["emitter"].last is None
    assert robot.devices["radio_rx"].sampling_period == 32 and robot.devices["receiver"].sampling_period is None

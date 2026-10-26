import sys
import types

import pytest
from fakes import World

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

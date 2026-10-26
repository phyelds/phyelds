"""
One controller for any robot: the world names the program, the devices of the robot do the rest.

A project's controller is ``from phyelds.webots import main`` and ``main()``; the world gives
the program and its options in the ``controllerArgs`` of each robot.
"""
import argparse
import importlib
import sys
from collections.abc import Callable, Mapping
from typing import Any

from phyelds.libraries.device import label, source
from phyelds.webots.aggregate_controller import AggregateController
from phyelds.webots.body import Body, _devices


def main() -> None:
    """Run the program that ``controllerArgs`` name on this robot, until the world ends."""
    from controller import Robot  # pylint: disable=import-error,import-outside-toplevel

    options = _parser().parse_args(sys.argv[1:])
    robot = Robot()
    is_source = robot.getName() == options.source
    aggregate_controller = AggregateController(
        robot, options.program,
        emitter=_name(robot, "Emitter"), receiver=_name(robot, "Receiver"),
        sensors=lambda: {source.name: is_source},
    )
    body = Body(robot)
    while robot.step(options.steps_per_round * int(robot.getBasicTimeStep())) != -1:
        aggregate_controller.run_round()
        body.act(aggregate_controller.outputs)
        if options.trace:
            _log(robot, "round", aggregate_controller.outputs)
    _log(robot, "final", aggregate_controller.outputs)


def _parser() -> argparse.ArgumentParser:
    """The options a world gives the controller, in ``controllerArgs``."""
    parser = argparse.ArgumentParser(prog="phyelds", description="Run a program on this robot.")
    parser.add_argument("program", type=_program, help="the program to run, as module:function")
    parser.add_argument("--source", help="the name of the robot that senses source")
    parser.add_argument("--steps-per-round", type=int, default=1,
                        help="steps of the world between two rounds; more run the world faster")
    parser.add_argument("--trace", action="store_true", help="log the label at every round")
    return parser


def _program(spec: str) -> Callable[[], Any]:
    """The function that ``spec``, ``module:function``, names."""
    module, _, function = spec.partition(":")
    return getattr(importlib.import_module(module), function)


def _log(robot: Any, when: str, outputs: Mapping[str, Any]) -> None:
    """Print the label of ``robot``, as the program sent it: Webots draws no text on a robot."""
    print(f"{robot.getName()} {when}: {label.read(outputs, default='')}", flush=True)


def _name(robot: Any, kind: str) -> str:
    """The name of the first device of ``robot`` of the class ``kind``."""
    return _devices(robot, kind)[0].getName()

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
    """
    Run the program that ``controllerArgs`` name on this robot, until the world ends.

    Raises:
        ValueError: If the robot has no ``Emitter`` or no ``Receiver``, or no ``GPS`` while
            ``--gps`` asks for one.
    """
    from controller import Robot  # pylint: disable=import-error,import-outside-toplevel

    options = _parser().parse_args(sys.argv[1:])
    robot = Robot()
    body = Body(
        robot, rgb_leds=not options.on_off_leds,
        wheel_radius=options.wheel_radius, max_speed=options.max_speed,
    )
    aggregate_controller = _aggregate_controller(robot, options, body)
    while robot.step(options.steps_per_round * int(robot.getBasicTimeStep())) != -1:
        aggregate_controller.run_round()
        body.act(aggregate_controller.outputs)
        if options.trace:
            _log(robot, "round", aggregate_controller.outputs)
    _log(robot, "final", aggregate_controller.outputs)


def _aggregate_controller(
    robot: Any, options: argparse.Namespace, body: Body
) -> AggregateController:
    """The rounds of the program of ``options`` on ``robot``, sensing also through ``body``."""
    emitter, receiver = _name(robot, "Emitter"), _name(robot, "Receiver")
    if emitter is None or receiver is None:
        raise ValueError(f"robot {robot.getName()!r} needs an Emitter and a Receiver")
    gps = _name(robot, "GPS") if options.gps else None
    if options.gps and gps is None:
        raise ValueError(f"robot {robot.getName()!r} needs a GPS to sense its position")
    is_source = robot.getName() == options.source
    return AggregateController(
        robot, options.program, emitter=emitter, receiver=receiver,
        gps=gps, inertial_unit=_name(robot, "InertialUnit"),
        sensors=lambda: {source.name: is_source, **body.sense()}, paths=options.paths,
    )


def _parser() -> argparse.ArgumentParser:
    """The options a world gives the controller, in ``controllerArgs``."""
    parser = argparse.ArgumentParser(prog="phyelds", description="Run a program on this robot.")
    parser.add_argument("program", type=_program, help="the program to run, as module:function")
    parser.add_argument("--source", help="the name of the robot that senses source")
    parser.add_argument("--gps", action="store_true", help="sense the position, from the GPS")
    parser.add_argument("--wheel-radius", type=float, help="the radius of the wheels, in metres")
    parser.add_argument("--max-speed", type=float, default=0.1, help="the top speed, in m/s")
    parser.add_argument("--on-off-leds", action="store_true",
                        help="the LEDs have a colour list: switch them on or off")
    parser.add_argument("--paths", choices=("compact", "debug"), default="compact",
                        help="the path mode of the engine: the same on every robot")
    parser.add_argument("--steps-per-round", type=int, default=1,
                        help="steps of the world between two rounds; more run the world faster")
    parser.add_argument("--trace", action="store_true", help="log the label at every round")
    return parser


def _program(spec: str) -> Callable[[], Any]:
    """The function that ``spec``, ``module:function``, names."""
    module, _, function = spec.partition(":")
    if not module or not function:
        raise argparse.ArgumentTypeError(f"{spec!r} is not module:function")
    return getattr(importlib.import_module(module), function)


def _log(robot: Any, when: str, outputs: Mapping[str, Any]) -> None:
    """Print the label of ``robot``, as the program sent it: Webots draws no text on a robot."""
    print(f"{robot.getName()} {when}: {label.read(outputs, default='')}", flush=True)


def _name(robot: Any, kind: str) -> str | None:
    """The name of the first device of ``robot`` of the class ``kind``; ``None`` without one."""
    return next((device.getName() for device in _devices(robot, kind)), None)

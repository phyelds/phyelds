"""
Lights: the network goes from green to yellow to red together, as one traffic light.

The phases are a collective state machine: the first device whose timer runs out moves
the whole network to the next phase, and the change spreads from it. The phases are
named after colours, and drawn in them. Change DURATION, or add devices while it runs.
"""
from enum import IntEnum

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import StateMachine
from phyelds.libraries.time import local_time, timer

DURATION = 8  # rounds a phase lasts


class Light(IntEnum):
    """The phases of the light."""

    GREEN = 0
    YELLOW = 1
    RED = 2


light = StateMachine(*Light)


def after(phase: Light, duration: float) -> None:
    """Move the network to ``phase`` once ``duration`` rounds have passed in this one."""
    if timer(duration) <= 0:
        light.go(phase, priority=-local_time())


@light.state(Light.GREEN, to=[Light.YELLOW])
def green() -> None:
    """Go."""
    after(Light.YELLOW, DURATION)


@light.state(Light.YELLOW, to=[Light.RED])
def yellow() -> None:
    """Slow down, for a shorter while."""
    after(Light.RED, DURATION / 2)


@light.state(Light.RED, to=[Light.GREEN])
def red() -> None:
    """Stop."""
    after(Light.GREEN, DURATION)


@aggregate
def traffic_light() -> Light:
    """The phase the device agrees on."""
    phase, _ = light.run()
    return phase

"""
One round of one device: the step every host repeats, whatever its devices and their messages.
"""
from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass
from typing import Any

from phyelds import engine
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine


@dataclass(frozen=True)
class Round:
    """What a round of a device leaves behind."""

    result: Any
    """What the program returned."""
    outbox: dict[str, Any]
    """The messages to send to the neighbors, keyed by alignment path."""
    state: dict[str, Any]
    """The state to give to the next round."""
    outputs: dict[str, Any]
    """What the program stored with ``store``."""


def run_round(  # pylint: disable=too-many-arguments
    program: Callable[[], Any],
    device: Hashable,
    sensors: Mapping[str, Any],
    inbox: Mapping[Hashable, Mapping[str, Any]],
    state: Mapping[str, Any] | None = None,
    *,
    paths: Any = "debug",
) -> Round:
    """
    Run ``program`` once on ``device``, on a fresh engine set as the current one.

    Args:
        program: The ``@aggregate`` function to run.
        device: The id of the device.
        sensors: The sensors of the device in this round, by name.
        inbox: The messages of the neighbors, by their id.
        state: The state left by the previous round; none on the first.
        paths: How the engine encodes alignment paths (see ``MutableEngine``).

    Returns:
        The result, messages, state and outputs of the round.
    """
    node_engine = MutableEngine(paths=paths)
    engine.set(node_engine)
    context = NodeContext(device, dict(sensors))
    node_engine.setup(context, inbox, state)
    result = program()
    outbox = node_engine.cooldown()  # first: it also drops the state not used
    return Round(
        result=result,
        outbox=outbox,
        state=node_engine.state_trace(),
        outputs=context.outputs,
    )

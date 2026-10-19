"""
Collective state machines: a finite state machine run by the whole network, whose states
are collective behaviours and whose transitions are collective agreements.

Each device runs the machine on its own and proposes transitions from what it senses; the
devices share the history of the transitions they went through and adopt the most
advanced one, so that a transition proposed by one device spreads to all of them. Two
devices that propose different transitions at once are in conflict: the one with the
higher priority wins, then the greater state. Based on *Macroscopic Design of Swarms with
Collective State Machines* (https://github.com/cric96/experiments-2025-collective-state-machines).
"""
from collections.abc import Callable
from dataclasses import dataclass
from functools import reduce
from typing import Any, TypeVar

from phyelds.calculus import aggregate, align, exchange
from phyelds.data.codec import register

S = TypeVar("S")


@dataclass(frozen=True)
class Next:
    """
    A transition to ``state``, with the ``priority`` that settles conflicts.

    A transition function that returns a bare state proposes it with the lowest priority.
    """

    state: Any
    priority: float = float("-inf")


@register
@dataclass(frozen=True)
class _MachineHistory:
    """The transitions of the machine, oldest first, each as ``(priority, state)``."""

    entries: tuple


def _newer(first: _MachineHistory, second: _MachineHistory) -> _MachineHistory:
    """
    The more advanced of two histories, comparing them entry by entry: a longer history
    wins over its own prefix, and the first differing transition decides between two
    that diverged.
    """
    return first if first.entries > second.entries else second


@aggregate
def collective_state_machine(initial: S, transition: Callable[[S], S | Next]) -> S:
    """
    Run a state machine on the whole network, so that all the devices agree on its state.

    Args:
        initial: The state the machine starts in. States are compared with ``==`` and,
            to settle conflicts of equal priority, with ``<``: use ints, strings or an
            ``IntEnum``. A state received from a device over a codec arrives as its plain
            value (an ``IntEnum`` as an ``int``).
        transition: Given the current state, the next one, as a bare state or as a
            ``Next`` with a priority; the current state itself to stay. It runs aligned on
            the current state, so the aggregate operations it calls in a state do not
            interact with those of the devices in other states.

    Returns:
        The state the device is in after this round.
    """
    start = _MachineHistory(((float("-inf"), initial),))
    set_histories, histories = exchange(start)
    own = histories.local()
    current = own.entries[-1][1]
    with align(current):
        proposal = transition(current)
    if not isinstance(proposal, Next):
        proposal = Next(proposal)
    if proposal.state != current:
        own = _MachineHistory(own.entries + ((proposal.priority, proposal.state),))
    agreed = reduce(_newer, histories, own)
    set_histories(agreed)
    return agreed.entries[-1][1]

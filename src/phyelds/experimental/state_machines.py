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
    """
    The transitions of the machine, oldest first, each as ``(priority, state)``, after the
    ``forgotten`` oldest ones.
    """

    forgotten: int
    entries: tuple

    def remember_last(self, memory: int | None) -> "_MachineHistory":
        """This history, with only its last ``memory`` transitions (all of them if ``None``)."""
        if memory is None or len(self.entries) <= memory:
            return self
        dropped = len(self.entries) - memory
        return _MachineHistory(self.forgotten + dropped, self.entries[dropped:])


def _newer(first: _MachineHistory, second: _MachineHistory) -> _MachineHistory:
    """
    The more advanced of two histories, comparing them entry by entry from the first one
    both remember: a longer history wins over its own prefix, and the first differing
    transition decides between two that diverged.
    """
    start = max(first.forgotten, second.forgotten)
    first_entries = first.entries[start - first.forgotten:]
    second_entries = second.entries[start - second.forgotten:]
    return first if first_entries > second_entries else second


@aggregate
def collective_state_machine(
    initial: S, transition: Callable[[S], S | Next], *, memory: int | None = None
) -> S:
    """
    Run a state machine on the whole network, so that all the devices agree on its state.

    Args:
        initial: The state the machine starts in. States are compared with ``==`` and,
            to settle conflicts of equal priority, with ``<``: use ints, strings or an
            ``IntEnum``. A state received from a device over a codec arrives as its plain
            value (an ``IntEnum`` as an ``int``).
        transition: Given the current state, the next one, as a bare state or as a
            ``Next`` with a priority; the current state itself to stay. It runs on the
            state the device agrees on with its neighbors in this round, and aligned on
            it, so the aggregate operations it calls in a state do not interact with
            those of the devices in other states. The next state is sent to the
            neighbors, and the device moves to it from the next round, if it wins.
        memory: How many transitions each device remembers, and sends to its neighbors;
            ``None`` remembers them all, and the messages grow with every transition.
            Two histories that diverged before what both remember are told apart by
            their last transitions only, so a short memory can settle a conflict
            differently.

    Returns:
        The state the device agreed on, and ran ``transition`` on, in this round.

    Raises:
        ValueError: If ``memory`` is less than 1.
    """
    if memory is not None and memory < 1:
        raise ValueError(f"memory must be at least 1, not {memory}")
    start = _MachineHistory(0, ((float("-inf"), initial),))
    set_histories, histories = exchange(start)
    agreed = histories.local()
    for history in histories:
        agreed = _newer(agreed, history)
    current = agreed.entries[-1][1]
    with align(current):
        proposal = transition(current)
    if not isinstance(proposal, Next):
        proposal = Next(proposal)
    if proposal.state != current:
        entries = agreed.entries + ((proposal.priority, proposal.state),)
        agreed = _MachineHistory(agreed.forgotten, entries)
    set_histories(agreed.remember_last(memory))
    return current

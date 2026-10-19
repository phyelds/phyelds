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
from collections.abc import Callable, Sequence
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


def _extend(history: _MachineHistory, proposal: Next) -> _MachineHistory:
    """
    Extend ``history`` with the prioritised state a program produced (Definition 4):
    a final self-loop is replaced, so that the history never loops but at its end.
    """
    entries = history.entries
    if len(entries) >= 2 and entries[-1][1] == entries[-2][1]:
        entries = entries[:-1]
    return _MachineHistory(history.forgotten, entries + ((proposal.priority, proposal.state),))


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
    set_histories(_extend(agreed, proposal).remember_last(memory))
    return current


class StateMachine:
    """
    A collective state machine described state by state: each state is a function that
    does what the device does in that state and, from what happens, proposes where to go.

    Example::

        mission = StateMachine("wait", "explore", "defend")

        @mission.state("wait", to=["explore", "defend"])
        def wait():
            if sense("attack"):
                mission.go("defend", priority=math.inf)
            elif sense("alarm"):
                mission.go("explore")
            return distance_to(sense("base"), neighbors_distances())

        state, distance = mission.run()

    Args:
        *states: The states, such as strings or the members of an enum. The machine
            starts in the first one, and a conflict of equal priority goes to the one
            declared later. Devices send the position of a state, not the state, so
            long names cost nothing in the messages.
        memory: How many transitions each device remembers, as in
            ``collective_state_machine``.

    Raises:
        ValueError: If there are no states, or the same state is declared twice.
    """

    def __init__(self, *states: Any, memory: int | None = None):
        if not states:
            raise ValueError("a state machine needs at least one state")
        if len(set(states)) != len(states):
            raise ValueError(f"the states must be distinct: {states}")
        self.states = states
        self.memory = memory
        self._behaviours: dict[Any, Callable[[], Any]] = {}
        self._targets: dict[Any, tuple] = {}
        self._proposals: list[Next] | None = None

    def state(self, name: Any, *, to: Sequence[Any] | None = None) -> Callable:
        """
        Decorate the function of the state ``name``.

        The function takes no arguments, and returns what the device does in the state
        (``run`` returns it). It runs on the state the device agrees on with its
        neighbors, aligned on it, and proposes a transition with ``go``; one that does
        not call ``go`` stays. A state without a function does nothing, and stays.

        Args:
            name: The state.
            to: The states the function may go to; ``go`` rejects any other. ``None``
                allows any, but leaves the transitions out of ``to_mermaid``.

        Returns:
            The decorator, which leaves the function unchanged.

        Raises:
            ValueError: If ``name``, or a state in ``to``, is not a state of the machine.
        """
        for state in (name, *(to or ())):
            self._index(state)

        def decorate(behaviour: Callable[[], Any]) -> Callable[[], Any]:
            self._behaviours[name] = behaviour
            if to is not None:
                self._targets[name] = tuple(to)
            return behaviour

        return decorate

    def go(self, target: Any, *, priority: float = float("-inf")) -> None:  # pylint: disable=invalid-name
        """
        Propose a transition to ``target``, from the function of the current state.

        If the function proposes more than one, the one that would win a conflict is kept.

        Args:
            target: The next state.
            priority: The priority of the transition, the lowest by default.

        Raises:
            RuntimeError: If no function of a state is running.
            ValueError: If ``target`` is not a state of the machine.
        """
        if self._proposals is None:
            raise RuntimeError("go proposes a transition from the function of a state")
        self._proposals.append(Next(self._index(target), priority))

    def run(self) -> tuple[Any, Any]:
        """
        Run a round of the machine on this device.

        Returns:
            The state the device agreed on, and what its function returned.

        Raises:
            ValueError: If the function of the state goes to a state it does not declare.
        """
        output = None

        def transition(index: int) -> int | Next:
            nonlocal output
            name = self.states[index]
            behaviour = self._behaviours.get(name)
            self._proposals = []
            try:
                output = behaviour() if behaviour else None
                proposals = self._proposals
            finally:
                self._proposals = None
            if not proposals:
                return index
            for proposal in proposals:
                self._check_target(name, self.states[proposal.state])
            return max(proposals, key=lambda proposal: (proposal.priority, proposal.state))

        index = collective_state_machine(0, transition, memory=self.memory)
        return self.states[index], output

    def to_mermaid(self) -> str:
        """
        The diagram of the transitions declared with ``to``, in Mermaid syntax; the
        members of an enum are drawn by name.
        """
        lines = ["stateDiagram-v2", f"    [*] --> {_label(self.states[0])}"]
        for source, targets in self._targets.items():
            lines.extend(f"    {_label(source)} --> {_label(target)}" for target in targets)
        return "\n".join(lines)

    def _index(self, state: Any) -> int:
        """The position of ``state`` among the states, which is what devices send."""
        if state not in self.states:
            raise ValueError(f"{state!r} is not a state of the machine: {self.states}")
        return self.states.index(state)

    def _check_target(self, source: Any, target: Any) -> None:
        """Reject a transition from ``source`` to a state it does not declare."""
        if source in self._targets and target not in self._targets[source]:
            raise ValueError(f"{source!r} goes to {target!r}, not among {self._targets[source]}")


def _label(state: Any) -> str:
    """How ``state`` is drawn: by name if it has one, as the member of an enum does."""
    return getattr(state, "name", str(state))

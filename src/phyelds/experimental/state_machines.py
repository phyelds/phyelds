"""
Collective state machines: a finite state machine run by the whole network, whose states
are collective behaviours and whose transitions are collective agreements.

The model of *Macroscopic Design of Swarms with Collective State Machines* (Aguzzi et al.,
ICCCI 2026, https://doi.org/10.1007/978-3-032-36868-3_28), whose definitions the comments
cite. Each device runs the program of its state and extends the history of the machine
with the prioritised state the program produces; the devices take the maximum of the
histories of their neighbors, so that a transition proposed by one device spreads to all
of them. Two devices that propose different transitions at once are in conflict: the one
with the higher priority wins, then the greater state.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

from phyelds.calculus import aggregate, align, exchange
from phyelds.data.codec import register
from phyelds.libraries.time import local_time

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
    A compressed history (Definition 7): the prioritised states the machine went through,
    oldest first, each as ``(priority, state, time)``, after the ``forgotten`` oldest ones.
    """

    forgotten: int
    entries: tuple


def _extend(history: _MachineHistory, proposal: Next, now: float) -> _MachineHistory:
    """
    Extend ``history`` with the prioritised state a program produced at time ``now``
    (Definition 4): a final self-loop is replaced, so that the history never loops but
    at its end.
    """
    entries = history.entries
    if len(entries) >= 2 and entries[-1][1] == entries[-2][1]:
        entries = entries[:-1]
    return _MachineHistory(history.forgotten, entries + ((proposal.priority, proposal.state, now),))


def _forget(history: _MachineHistory, now: float, window: float) -> _MachineHistory:
    """
    Forget the entries older than ``window`` at time ``now``, keeping at least two, so
    that a final self-loop can still be told (Section 3.1).
    """
    entries = history.entries
    old = 0
    while old < len(entries) and now - entries[old][2] > window:
        old += 1
    old = min(old, max(len(entries) - 2, 0))
    if old == 0:
        return history
    return _MachineHistory(history.forgotten + old, entries[old:])


def _aligned(history: _MachineHistory) -> list:
    """The aligned sequence of ``history``: ``None`` for each forgotten entry, then the others."""
    return [None] * history.forgotten + list(history.entries)


def _first_incompatibility(first: list, second: list) -> int | None:
    """The first index where two aligned sequences remember different prioritised states."""
    for index, (mine, theirs) in enumerate(zip(first, second)):
        if mine is not None and theirs is not None and mine[:2] != theirs[:2]:
            return index
    return None


def _merge(histories: Sequence[_MachineHistory]) -> _MachineHistory:
    """
    The maximum of compressed histories (Definition 8): drop each history smaller than
    another at their first incompatible entry, then take, entry by entry, the earliest of
    those the others remember. Without forgotten entries, it is the lexicographic maximum
    of Definition 5, a prefix being smaller.
    """
    sequences = [_aligned(history) for history in histories]
    discarded = set()
    # ponytail: pairwise, quadratic in the number of neighbors; fine for neighborhoods
    for first, mine in enumerate(sequences):
        for second in range(first + 1, len(sequences)):
            theirs = sequences[second]
            index = _first_incompatibility(mine, theirs)
            if index is not None:
                discarded.add(first if mine[index][:2] < theirs[index][:2] else second)
    # Comparing with forgotten entries is not transitive: should every history lose to
    # another, keep the first, the device's own.
    survivors = [sequence for index, sequence in enumerate(sequences) if index not in discarded]
    survivors = survivors or sequences[:1]
    merged = []
    for index in range(max(len(sequence) for sequence in survivors)):
        remembered = [sequence[index] for sequence in survivors if index < len(sequence)]
        remembered = [entry for entry in remembered if entry is not None]
        merged.append(min(remembered, key=lambda entry: entry[2]) if remembered else None)
    # A compressed history remembers a contiguous tail: whatever precedes a gap is forgotten.
    kept = max((index + 1 for index, entry in enumerate(merged) if entry is None), default=0)
    return _MachineHistory(kept, tuple(merged[kept:]))


@aggregate
def collective_state_machine(
    initial: S,
    transition: Callable[[S], S | Next],
    *,
    window: float | None = None,
    clock: float | None = None,
) -> S:
    """
    Run a collective state machine (Definition 6): every device agrees on the history of
    the machine with its neighbors, runs the program of its last state, and extends the
    history with what the program produced.

    Args:
        initial: The state the machine starts in, with the lowest priority. States are
            compared with ``==`` and, to settle conflicts of equal priority, with ``<``:
            use ints, strings or an ``IntEnum``. A state received from a device over a
            codec arrives as its plain value (an ``IntEnum`` as an ``int``).
        transition: The program of the states: given the current state, the prioritised
            state it produces, as a ``Next`` or as a bare state with the lowest priority;
            the current state to stay. It runs aligned on the current state, so the
            aggregate operations it calls in a state do not interact with those of the
            devices in other states. Staying is recorded too, with its priority: a
            transition with the same priority to a smaller state loses to it, and does
            not spread.
        window: Compress the history (Section 3.1): forget the entries older than
            ``window`` time units, keeping at least two. If ``window`` is longer than the
            time a message takes to cross the network, the machine behaves as with the
            whole history, which ``None`` keeps.
        clock: The time on an approximately shared clock, used with ``window``;
            ``local_time()`` if ``None``.

    Returns:
        The state the device agreed on, and ran ``transition`` on, in this round.

    Raises:
        ValueError: If ``window`` is not positive, or there is a window but no clock.
    """
    if window is not None and window <= 0:
        raise ValueError(f"window must be positive, not {window}")
    now = local_time() if clock is None else clock
    if window is not None and now is None:
        raise ValueError("a window needs a clock: sense the time, or pass clock")
    now = 0.0 if now is None else now
    start = _MachineHistory(0, ((float("-inf"), initial, now),))
    set_histories, histories = exchange(start)
    agreed = _merge(list(histories))
    current = agreed.entries[-1][1]
    with align(current):
        proposal = transition(current)
    if not isinstance(proposal, Next):
        proposal = Next(proposal)
    extended = _extend(agreed, proposal, now)
    set_histories(extended if window is None else _forget(extended, now, window))
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
        window: Forget the history older than ``window`` time units, as in
            ``collective_state_machine``; ``None`` keeps it all.


    Raises:
        ValueError: If there are no states, or the same state is declared twice.
    """

    def __init__(self, *states: Any, window: float | None = None):
        if not states:
            raise ValueError("a state machine needs at least one state")
        if len(set(states)) != len(states):
            raise ValueError(f"the states must be distinct: {states}")
        self.states = states
        self.window = window
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

        The state produces the greatest of staying, with the lowest priority, and the
        transitions it proposes (Remark 1 of the paper): a transition to an earlier state
        needs a higher priority, such as the negated time, to happen.

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

    def run(self, *, clock: float | None = None) -> tuple[Any, Any]:
        """
        Run a round of the machine on this device.

        Args:
            clock: The time used with the window; ``local_time()`` if ``None``.

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
            for proposal in proposals:
                self._check_target(name, self.states[proposal.state])
            # Remark 1: the program produces the greatest of staying and its transitions.
            options = [Next(index), *proposals]
            return max(options, key=lambda option: (option.priority, option.state))

        index = collective_state_machine(0, transition, window=self.window, clock=clock)
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

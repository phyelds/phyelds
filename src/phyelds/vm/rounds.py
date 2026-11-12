"""
Rounds of devices: the step every host repeats, whatever its devices and their messages, for
one device or for many that do not depend on each other.
"""
from collections.abc import Callable, Hashable, Mapping, Sequence
# In Python 3.14 concurrent.futures loads ThreadPoolExecutor in __getattr__, which astroid misses.
from concurrent.futures import ThreadPoolExecutor  # pylint: disable=no-name-in-module
from dataclasses import dataclass
import math
from typing import Any

from phyelds import engine
from phyelds.vm import Engine, NodeContext
from phyelds.vm.internal import MutableEngine

# More chunks than workers, so that a worker that drew slow devices does not hold the others.
_CHUNKS_PER_WORKER = 4


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
    engine_instance: Engine | None = None,
) -> Round:
    """
    Run ``program`` once on ``device``, setting the round engine as the current one.

    Args:
        program: The ``@aggregate`` function to run.
        device: The id of the device.
        sensors: The sensors of the device in this round, by name.
        inbox: The messages of the neighbors, by their id.
        state: The state left by the previous round; none on the first.
        paths: How the engine encodes alignment paths when creating a ``MutableEngine``.
        engine_instance: Optional pre-built ``Engine`` to reuse across rounds.

    Returns:
        The result, messages, state and outputs of the round.
    """
    node_engine = MutableEngine(paths=paths) if engine_instance is None else engine_instance
    engine.set(node_engine)
    context = NodeContext(device, sensors)  # type: ignore[arg-type]
    node_engine.setup(context, inbox, state)  # type: ignore[arg-type]
    result = program()
    outbox = node_engine.cooldown()  # first: it also drops the state not used
    return Round(
        result=result,
        outbox=outbox,
        state=node_engine.state_trace(),
        outputs=context.outputs,
    )


@dataclass(frozen=True)
class Rounds:
    """What the rounds of many devices leave behind, by device id."""

    results: dict[Hashable, Any]
    """What the program returned on each device."""
    outboxes: dict[Hashable, dict[str, Any]]
    """The messages each device sends to its neighbors, keyed by alignment path."""
    states: dict[Hashable, dict[str, Any]]
    """The state each device gives to its next round."""
    outputs: dict[Hashable, dict[str, Any]]
    """What the program stored with ``store`` on each device."""


class RoundRunner:  # pylint: disable=too-few-public-methods
    """
    Runs the rounds of many devices that do not depend on each other: what a device reads
    comes from its inbox and its state, never from the rounds run with it.

    The rounds can run in a pool of ``workers`` threads: the results are the same, and they
    take less time on a free-threaded Python (3.14t), where threads run in parallel. Elsewhere
    one thread at a time runs Python code, so more workers only add their cost. With one
    worker, the calling thread runs the rounds on one engine, kept from a run to the next.

    Args:
        program: The ``@aggregate`` function to run on each device.
        workers: How many threads run the rounds; with 1, the calling thread runs them.
        paths: Alignment path encoding for the default ``MutableEngine`` (``"compact"`` by
            default).
        engine_factory: Optional factory building one ``Engine`` per thread.

    Raises:
        ValueError: If ``workers`` is below 1.
    """

    def __init__(
        self,
        program: Callable[[], Any],
        *,
        workers: int = 1,
        paths: Any = "compact",
        engine_factory: Callable[[], Engine] | None = None,
    ):
        if workers < 1:
            raise ValueError(f"workers must be at least 1, not {workers}")
        self.program = program
        self.workers = workers
        self._make_engine: Callable[[], Engine] = (
            engine_factory if engine_factory is not None else lambda: MutableEngine(paths=paths)
        )
        self._engine: Engine | None = None

    def run(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        inbox_of: Callable[[Hashable], Mapping[Hashable, Mapping[str, Any]]],
        states: Mapping[Hashable, Mapping[str, Any]],
    ) -> Rounds:
        """
        Run the program once on each device of ``sensors``.

        Args:
            sensors: The sensors of each device to run, by its id.
            inbox_of: The messages a device reads, by the id of their sender, given its id.
            states: The state each device left in its previous round, by its id; a device
                missing from it runs its first round.

        Returns:
            What the rounds leave behind, by device id, in the order of ``sensors``.
        """
        devices = list(sensors)
        if self.workers == 1:
            if self._engine is None:
                self._engine = self._make_engine()
            return self._run(devices, sensors, inbox_of, states, node_engine=self._engine)
        # A pool per run: starting its threads costs far less than rounds worth splitting.
        with ThreadPoolExecutor(self.workers) as pool:
            parts = list(pool.map(
                lambda chunk: self._run(
                    chunk, sensors, inbox_of, states, node_engine=self._make_engine()
                ),
                _chunks(devices, self.workers),
            ))
        return _merge(parts)

    def _run(  # pylint: disable=too-many-arguments
        self,
        devices: Sequence[Hashable],
        sensors: Mapping[Hashable, Mapping[str, Any]],
        inbox_of: Callable[[Hashable], Mapping[Hashable, Mapping[str, Any]]],
        states: Mapping[Hashable, Mapping[str, Any]],
        *,
        node_engine: Engine,
    ) -> Rounds:
        """The rounds of ``devices``, on the calling thread."""
        engine.set(node_engine)
        program = self.program
        done = Rounds({}, {}, {}, {})
        for device in devices:
            context = NodeContext(device, sensors[device])  # type: ignore[arg-type]
            inbox, state = inbox_of(device), states.get(device)
            node_engine.setup(context, inbox, state)  # type: ignore[arg-type]
            done.results[device] = program()
            done.outboxes[device] = node_engine.cooldown()  # first: it also drops unused state
            done.states[device] = node_engine.state_trace()
            done.outputs[device] = context.outputs
        return done


def _chunks(devices: Sequence[Hashable], workers: int) -> list[Sequence[Hashable]]:
    """``devices`` split into about ``_CHUNKS_PER_WORKER`` chunks per worker, in their order."""
    size = max(1, math.ceil(len(devices) / (workers * _CHUNKS_PER_WORKER)))
    return [devices[start:start + size] for start in range(0, len(devices), size)]


def _merge(parts: Sequence[Rounds]) -> Rounds:
    """The rounds of all the chunks, in their order."""
    if len(parts) == 1:
        return parts[0]
    merged = Rounds({}, {}, {}, {})
    for part in parts:
        merged.results.update(part.results)
        merged.outboxes.update(part.outboxes)
        merged.states.update(part.states)
        merged.outputs.update(part.outputs)
    return merged

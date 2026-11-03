"""
Synchronous rounds of many devices in one process: the building block of hosts that step all
their agents together, such as the model of a multi-agent simulator.
"""
import math
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from phyelds import engine
from phyelds.data import State
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine

# More chunks than workers, so that a worker that drew slow devices does not hold the others.
_CHUNKS_PER_WORKER = 4

_Round = tuple[dict[Hashable, Any], dict[Hashable, Any], dict[Hashable, Any], dict[Hashable, Any]]


class SynchronousRuntime:
    """
    Runs an aggregate program on many devices, one synchronous round at a time.

    In a round every device receives what its neighbors sent in the previous round, so the
    result does not depend on the order of the devices. The devices are known by their ids,
    and the host gives their sensors and neighbors at each round.

    The rounds of the devices are independent, so they can run in a pool of ``workers``
    threads: the results are the same, and they take less time on a free-threaded Python
    (3.14t), where threads run in parallel. Elsewhere one thread at a time runs Python code,
    so more workers only add their cost.

    Args:
        program: The ``@aggregate`` function to run on each device.
        workers: How many threads run the rounds of the devices; with 1, the calling thread
            runs them.

    Raises:
        ValueError: If ``workers`` is below 1.
    """

    def __init__(self, program: Callable[[], Any], *, workers: int = 1):
        if workers < 1:
            raise ValueError(f"workers must be at least 1, not {workers}")
        self.program = program
        self.workers = workers
        self.outputs: dict[Hashable, dict[str, Any]] = {}
        """What the program stored with ``store`` on each device, in the last round."""
        self._states: dict[Hashable, dict[str, Any]] = {}
        self._outboxes: dict[Hashable, dict[str, Any]] = {}

    def run_round(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> dict[Hashable, Any]:
        """
        Run the program once on each device of ``sensors``.

        A device missing from a round is forgotten: its state and messages are dropped.

        Args:
            sensors: The sensors of each device of this round, by its id.
            neighbors: The ids of the neighbors of each device, by its id.

        Returns:
            The result of the program on each device, by its id, in the order of ``sensors``.
        """
        devices = list(sensors)
        if self.workers == 1:
            parts = [self._run(devices, sensors, neighbors)]
        else:
            # A pool per round: starting its threads costs far less than a round worth splitting.
            with ThreadPoolExecutor(self.workers) as pool:
                chunks = _chunks(devices, self.workers)
                parts = list(pool.map(lambda chunk: self._run(chunk, sensors, neighbors), chunks))
        self._states, self._outboxes, self.outputs, results = _merge(parts)
        return results

    def reset(self) -> None:
        """Forget the state and the messages of every device."""
        self._states, self._outboxes, self.outputs = {}, {}, {}

    def _run(
        self,
        devices: Sequence[Hashable],
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> _Round:
        """The rounds of ``devices``: their states, outboxes, outputs and results."""
        states, outboxes, outputs, results = {}, {}, {}, {}
        for device in devices:
            inbox = {
                other: self._outboxes[other]
                for other in neighbors.get(device, ())
                if other in self._outboxes
            }
            node_engine = MutableEngine()
            engine.set(node_engine)
            context = NodeContext(device, dict(sensors[device]))
            node_engine.setup(context, inbox, self._states.get(device, {}))
            result = self.program()
            outboxes[device] = node_engine.cooldown()
            states[device] = node_engine.state_trace()
            outputs[device] = context.outputs
            results[device] = result.value if isinstance(result, State) else result
        return states, outboxes, outputs, results


def _chunks(devices: Sequence[Hashable], workers: int) -> list[Sequence[Hashable]]:
    """``devices`` split into about ``_CHUNKS_PER_WORKER`` chunks per worker, in their order."""
    size = max(1, math.ceil(len(devices) / (workers * _CHUNKS_PER_WORKER)))
    return [devices[start:start + size] for start in range(0, len(devices), size)]


def _merge(parts: Iterable[_Round]) -> _Round:
    """The rounds of all the chunks, in their order."""
    merged: _Round = ({}, {}, {}, {})
    for part in parts:
        for whole, piece in zip(merged, part):
            whole.update(piece)
    return merged

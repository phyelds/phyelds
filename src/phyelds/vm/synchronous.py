"""
Synchronous rounds of many devices in one process: the building block of hosts that step all
their agents together, such as the model of a multi-agent simulator.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any

from phyelds.vm import Engine
from phyelds.vm.rounds import RoundRunner


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
        paths: Alignment path encoding for the default ``MutableEngine`` (``"compact"`` by
            default).
        engine_factory: Optional factory building one ``Engine`` per worker thread.

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
        self._runner = RoundRunner(
            program, workers=workers, paths=paths, engine_factory=engine_factory
        )
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
        sent = self._outboxes

        def inbox_of(device: Hashable) -> dict[Hashable, dict[str, Any]]:
            return {other: sent[other] for other in neighbors.get(device, ()) if other in sent}

        done = self._runner.run(sensors, inbox_of, self._states)
        self._states, self._outboxes, self.outputs = done.states, done.outboxes, done.outputs
        return done.results

    def reset(self) -> None:
        """Forget the state and the messages of every device."""
        self._states, self._outboxes, self.outputs = {}, {}, {}

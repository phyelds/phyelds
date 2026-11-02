"""
Synchronous rounds of many devices in one process: the building block of hosts that step all
their agents together, such as the model of a multi-agent simulator.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any

from phyelds import engine
from phyelds.data import State
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine


class SynchronousRuntime:
    """
    Runs an aggregate program on many devices, one synchronous round at a time.

    In a round every device receives what its neighbors sent in the previous round, so the
    result does not depend on the order of the devices. The devices are known by their ids,
    and the host gives their sensors and neighbors at each round.

    Args:
        program: The ``@aggregate`` function to run on each device.
    """

    def __init__(self, program: Callable[[], Any]):
        self.program = program
        self._states: dict[Hashable, dict[str, Any]] = {}
        self._outboxes: dict[Hashable, dict[str, Any]] = {}

    def run_round(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> dict[Hashable, Any]:
        """
        Run the program once on each device of ``sensors``.

        Args:
            sensors: The sensors of each device of this round, by its id.
            neighbors: The ids of the neighbors of each device, by its id.

        Returns:
            The result of the program on each device, by its id.
        """
        states, outboxes, results = {}, {}, {}
        for device, device_sensors in sensors.items():
            inbox = {
                other: self._outboxes[other]
                for other in neighbors.get(device, ())
                if other in self._outboxes
            }
            node_engine = MutableEngine()
            engine.set(node_engine)
            context = NodeContext(device, dict(device_sensors))
            node_engine.setup(context, inbox, self._states.get(device, {}))
            result = self.program()
            outboxes[device] = node_engine.cooldown()
            states[device] = node_engine.state_trace()
            results[device] = result.value if isinstance(result, State) else result
        self._states, self._outboxes = states, outboxes
        return results

    def reset(self) -> None:
        """Forget the state and the messages of every device."""
        self._states, self._outboxes = {}, {}

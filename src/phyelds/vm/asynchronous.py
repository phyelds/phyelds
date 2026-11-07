"""
Asynchronous rounds of many devices in one process: each device sends right after its own
round (a spike), so the next devices to run already read its new message.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any

from phyelds import engine
from phyelds.data import State
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine


class AsynchronousRuntime:
    """
    Runs an aggregate program on many devices, one spike or sequential round at a time.

    When a device runs, it reads the last messages its current neighbors sent and publishes
    its new message right away, so the next devices to run read it in the same step.

    Args:
        program: The ``@aggregate`` function to run on each device.
    """

    def __init__(self, program: Callable[[], Any]):
        self.program = program
        self.outputs: dict[Hashable, dict[str, Any]] = {}
        """What the program stored with ``store`` on each device, in its last spike."""
        self._states: dict[Hashable, dict[str, Any]] = {}
        self._outboxes: dict[Hashable, dict[str, Any]] = {}

    def spike(
        self,
        device: Hashable,
        sensors: Mapping[str, Any],
        neighbors: Iterable[Hashable],
    ) -> Any:
        """
        Run the program once on ``device``, keeping the state and messages of the others.

        Args:
            device: The id of the device running the spike.
            sensors: The sensors of ``device`` in this spike, by name.
            neighbors: The ids of the current neighbors of ``device``.

        Returns:
            The result of the program on ``device``.
        """
        inbox = {other: self._outboxes[other] for other in neighbors if other in self._outboxes}
        node_engine = MutableEngine()
        engine.set(node_engine)
        context = NodeContext(device, dict(sensors))
        node_engine.setup(context, inbox, self._states.get(device, {}))
        result = self.program()
        self._outboxes[device] = node_engine.cooldown()
        self._states[device] = node_engine.state_trace()
        self.outputs[device] = context.outputs
        return result.value if isinstance(result, State) else result

    def run_round(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> dict[Hashable, Any]:
        """
        Run the program once on each device of ``sensors``, in the order of ``sensors``.

        Args:
            sensors: The sensors of each device of this round, by its id.
            neighbors: The ids of the neighbors of each device, by its id.

        Returns:
            The result of the program on each device, by its id, in the order of ``sensors``.
        """
        return {
            device: self.spike(device, device_sensors, neighbors.get(device, ()))
            for device, device_sensors in sensors.items()
        }

    def forget(self, device: Hashable) -> None:
        """
        Forget the state, the messages and the outputs of ``device``.

        Args:
            device: The id of the device to forget.
        """
        self._states.pop(device, None)
        self._outboxes.pop(device, None)
        self.outputs.pop(device, None)

    def reset(self) -> None:
        """Forget the state and the messages of every device."""
        self._states, self._outboxes, self.outputs = {}, {}, {}

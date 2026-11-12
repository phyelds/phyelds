"""
Synchronous rounds of every device at once, on a torch device: in a round each device reads
what its neighbors sent in the previous one, as ``phyelds.vm.synchronous.SynchronousRuntime``
does, with one row per device instead of one round per device.
"""
from collections.abc import Callable, Mapping
from typing import Any

from phyelds import engine
from phyelds.gpu.engine import BatchEngine, Rows, States, SynchronousMessages, _written
from phyelds.gpu.topology import GraphTopology


class BatchSynchronousRuntime:
    """
    Runs an aggregate program on every device of a graph at once, one synchronous round at a
    time, on the torch device of the graph.

    Args:
        program: The ``@aggregate`` function to run; it runs once per round, for all the
            devices, with a row per device in each value.
        topology: Who hears whom.
    """

    def __init__(self, program: Callable[[], Any], topology: GraphTopology):
        self.program = program
        self.topology = topology
        self.outputs: dict[str, Rows] = {}
        """What the devices stored, by name: a value of each device and whether it stored one."""
        self._edges = topology.batch()
        self._states = States(topology.num_devices, topology.device)
        self._messages = SynchronousMessages(topology.num_devices, topology.device)

    def run_round(self, sensors: Mapping[str, Any]) -> Any:
        """
        Run the program once on every device.

        Args:
            sensors: The sensors of the devices, by name: a tensor with a row per device, or
                one value for all.

        Returns:
            What the program returned: a tensor with a row per device for each value, or a
                single value if it is the same for every device.
        """
        batch = BatchEngine(self._edges, self._states, self._messages, sensors)
        token = engine.set(batch)
        try:
            result = self.program()
        finally:
            engine.reset(token)
        devices = self._edges.devices
        self._messages.publish(devices, batch.finish())
        count = self.topology.num_devices
        for name, (values, stored) in batch.node_context.stored.items():
            self.outputs[name] = _written(None, count, devices, values, stored)
        return result

    def reset(self) -> None:
        """Forget the state, the messages and the outputs of every device."""
        self._states.clear()
        self._messages.clear()
        self.outputs = {}

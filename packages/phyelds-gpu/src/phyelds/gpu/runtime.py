"""
Synchronous rounds of every device at once, on a torch device: in a round each device reads
what its neighbors sent in the previous one, as ``phyelds.vm.synchronous.SynchronousRuntime``
does, with one row per device instead of one round per device.
"""
from collections.abc import Callable, Mapping
from typing import Any

import torch

from phyelds.gpu.engine import BatchEngine
from phyelds.gpu.memory import Rows, States, SynchronousMessages, write_rows
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
        self._states = States(topology)
        self._messages = SynchronousMessages(topology)

    def run_round(
        self, sensors: Mapping[str, Any], *, topology: GraphTopology | None = None
    ) -> Any:
        """
        Run the program once on every device.

        Args:
            sensors: The sensors of the devices, by name: a tensor with a row per device, or
                one value for all.
            topology: Who hears whom from this round on, for devices that move; the current
                graph by default. What a device sent to all its neighbors reaches those of
                the new graph; what is kept along an edge stays only if the edge does.

        Returns:
            What the program returned: a tensor with a row per device for each value, or a
                single value if it is the same for every device.

        Raises:
            ValueError: If ``topology`` links another number of devices.
        """
        if topology is not None and topology is not self.topology:
            self._move_to(topology)
        batch = BatchEngine(self._edges, self._states, self._messages, sensors)
        result = batch.run(self.program)
        devices = self._edges.devices
        self._messages.publish(self._edges, batch.finish())
        count = self.topology.num_devices
        for name, (values, stored) in batch.node_context.stored.items():
            self.outputs[name] = write_rows(None, count, devices, values, stored)
        return result

    def _move_to(self, topology: GraphTopology) -> None:
        """Make ``topology`` the graph of the next rounds, moving what is kept along edges."""
        index, kept = topology.edges_from(self.topology)
        self._states.move_to(topology, index, kept)
        self._messages.move_to(topology, index, kept)
        self.topology = topology
        self._edges = topology.batch()

    def reset(self, devices: torch.Tensor | None = None) -> None:
        """
        Forget the state, the messages and the outputs of ``devices``, as if they joined now.

        The others keep theirs, and stop hearing what ``devices`` sent, as for devices that
        leave ``SynchronousRuntime`` and come back.

        Args:
            devices: The ids of the devices to forget (``int64 [M]``); every device by default.

        Raises:
            ValueError: If an id is not one of a device of the graph.
        """
        if devices is None:
            self._states.clear()
            self._messages.clear()
            self.outputs = {}
            return
        devices = self._known(devices)
        self._states.forget_devices(devices)
        self._messages.forget_devices(devices)
        for _, stored in self.outputs.values():
            stored[devices] = False

    def _known(self, devices: torch.Tensor) -> torch.Tensor:
        """``devices`` as ids on the torch device of the graph, if they are all in it."""
        devices = devices.to(device=self.topology.device, dtype=torch.int64)
        count = self.topology.num_devices
        if devices.numel() and bool(((devices < 0) | (devices >= count)).any()):
            raise ValueError(f"the graph has devices 0 to {count - 1}, not {devices.tolist()}")
        return devices

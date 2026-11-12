"""
This module contains the event to run the aggregate program in the simulator.
"""
from abc import ABC
from collections.abc import Callable
from typing import Any

from phyelds import engine
from phyelds.simulator import Node, Simulator
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine


class SimulatorNodeContext(NodeContext, ABC):
    """
    A class to represent the context of a node in the simulator.
    This class exposes the node's data and position as sensors without copying ``node.data``.
    """

    def __init__(
        self,
        node_id: Any,
        sensors: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        *,
        default_position: tuple[float, ...] | None = None,
    ):
        super().__init__(node_id, sensors, outputs)
        self._default_position = default_position

    @staticmethod
    def from_node(node: Node) -> "SimulatorNodeContext":
        """
        Create the context of a simulated node backed by ``node.data`` and ``node.position``.

        Args:
            node: The node to create the context from.

        Returns:
            The node's ``SimulatorNodeContext``.
        """
        return SimulatorNodeContext(node.id, node.data, default_position=node.position)

    def sense(self, sensor_name: str) -> Any:
        if sensor_name == "position" and "position" not in self.sensors:
            return self._default_position
        return self.sensors.get(sensor_name)

    def position(self) -> Any:
        return self.sensors.get("position", self._default_position)


def aggregate_program_runner(
    simulator: Simulator,
    time_delta: float,
    node: Node,
    program: Callable[..., Any],
    **kwargs: Any,
) -> None:
    """
    Run ``program`` once for ``node`` and reschedule its next round after ``time_delta``.

    Args:
        simulator: The simulator owning ``node``.
        time_delta: Period until the next round of ``node``.
        node: The simulated node executing the round.
        program: The aggregate program to run.
        **kwargs: Keyword arguments forwarded to ``program``.
    """
    if node.id not in simulator.environment.nodes:
        return
    node.data["time"] = simulator.current_time
    all_neighbors = simulator.environment.get_neighbors(node)
    neighbors_messages = {
        neighbor.id: neighbor.data.get("messages", {}) for neighbor in all_neighbors
    }
    context = SimulatorNodeContext.from_node(node)
    node_engine = MutableEngine()
    engine.set(node_engine)
    node_engine.setup(context, neighbors_messages, node.data.get("state", {}))
    node.data["result"] = program(**kwargs)
    node.data["messages"] = node_engine.cooldown()
    node.data["state"] = node_engine.state_trace()
    node.data["outputs"] = context.outputs
    simulator.schedule_event(
        time_delta, aggregate_program_runner, simulator, time_delta, node, program, **kwargs
    )


def schedule_program_for_all(
    simulator: Simulator,
    start: float,
    frequency: float,
    program: Callable[..., Any],
    **kwargs: Any,
) -> None:
    """
    Run an aggregate program on every node of the simulator, round after round.

    Each node runs its first round ``start`` time units from now and then one every
    ``frequency`` time units; its result, outgoing messages, state and outputs are
    kept in its ``data``.

    Args:
        simulator: The simulator whose nodes run the program.
        start: The delay before the first round.
        frequency: The time between two rounds of a node (a period, not a rate).
        program: The aggregate program to run.
        **kwargs: Keyword arguments passed to ``program`` at each round.
    """
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(
            start, aggregate_program_runner, simulator, frequency, node, program, **kwargs
        )

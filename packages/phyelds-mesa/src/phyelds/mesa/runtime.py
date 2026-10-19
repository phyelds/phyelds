"""
Run phyelds programs on the agents of a Mesa model.

Each agent is a device: its ``unique_id`` is the device id, its neighbors are chosen by a
function of the agent, and the program runs once per agent in each round.
"""
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from mesa import Agent

from phyelds import engine
from phyelds.data import State
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine

Neighbors = Callable[[Agent], Iterable[Agent]]
Sensors = Callable[[Agent], Mapping[str, Any]]


class AggregateRuntime:
    """
    Runs an aggregate program on Mesa agents, one synchronous round at a time.

    In a round every agent receives what its neighbors sent in the previous round, so the
    result does not depend on the order of the agents. Call ``run_round`` from the
    ``step`` of the model.

    Args:
        program: The ``@aggregate`` function to run on each agent.
        neighbors: The agents a given agent talks to, e.g. ``within(radius)`` in a
            continuous space or ``cell_neighbors`` in a grid.
        sensors: Extra sensors of a given agent, added to ``position`` (its position, or
            the coordinate of its cell) and ``time`` (the time of the model).
    """

    def __init__(
        self, program: Callable[[], Any], *, neighbors: Neighbors, sensors: Sensors | None = None
    ):
        self.program = program
        self.neighbors = neighbors
        self.sensors = sensors
        self.outputs: dict[int, dict[str, Any]] = {}
        """What the program stored with ``store`` on each agent, in the last round."""
        self._states: dict[int, dict[str, Any]] = {}
        self._outboxes: dict[int, dict[str, Any]] = {}

    def run_round(self, agents: Iterable[Agent]) -> dict[int, Any]:
        """
        Run the program once on each of ``agents``.

        Agents missing from a round are forgotten: their state and messages are dropped.

        Args:
            agents: The agents of this round, e.g. ``model.agents``.

        Returns:
            The result of the program on each agent, by ``unique_id``.
        """
        states, outboxes, outputs, results = {}, {}, {}, {}
        for agent in agents:
            inbox = {
                neighbor.unique_id: self._outboxes[neighbor.unique_id]
                for neighbor in self.neighbors(agent)
                if neighbor.unique_id in self._outboxes
            }
            node_engine = MutableEngine()
            engine.set(node_engine)
            context = NodeContext(agent.unique_id, self._sense(agent))
            node_engine.setup(context, inbox, self._states.get(agent.unique_id, {}))
            result = self.program()
            outboxes[agent.unique_id] = node_engine.cooldown()
            states[agent.unique_id] = node_engine.state_trace()
            outputs[agent.unique_id] = context.outputs
            results[agent.unique_id] = result.value if isinstance(result, State) else result
        self._states, self._outboxes, self.outputs = states, outboxes, outputs
        return results

    def reset(self) -> None:
        """Forget the state and the messages of every agent."""
        self._states, self._outboxes, self.outputs = {}, {}, {}

    def _sense(self, agent: Agent) -> dict[str, Any]:
        """The default sensors of ``agent``, updated with the extra ones."""
        sensors = {"position": _position(agent), "time": agent.model.time}
        if self.sensors is not None:
            sensors.update(self.sensors(agent))
        return sensors


def within(radius: float) -> Neighbors:
    """
    Neighbors in a continuous space: the agents closer than ``radius``.

    Args:
        radius: The communication range.

    Returns:
        A function giving the neighbors of a ``ContinuousSpaceAgent``.
    """
    return lambda agent: agent.get_neighbors_in_radius(radius)[0]


def cell_neighbors(agent: Agent) -> list[Agent]:
    """
    Neighbors in a grid or network: the other agents in the cell of ``agent`` and around it.

    Args:
        agent: A ``CellAgent``.

    Returns:
        The agents of its cell, but itself, and of the neighborhood of its cell.
    """
    same_cell = [other for other in agent.cell.agents if other is not agent]
    return same_cell + list(agent.cell.neighborhood.agents)


def _position(agent: Agent) -> tuple | None:
    """Where ``agent`` is: its position in a continuous space, or the coordinate of its cell."""
    position = getattr(agent, "position", None)
    if position is not None:
        return tuple(float(coordinate) for coordinate in position)
    cell = getattr(agent, "cell", None)
    return None if cell is None else cell.coordinate

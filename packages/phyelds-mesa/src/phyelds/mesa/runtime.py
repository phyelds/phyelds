"""
Run phyelds programs on the agents of a Mesa model.

Each agent is a device: its ``unique_id`` is the device id, its neighbors are chosen by a
function of the agent, and the program runs once per agent in each round.
"""
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from mesa import Agent

from phyelds.vm.asynchronous import AsynchronousRuntime
from phyelds.vm.synchronous import SynchronousRuntime

Neighbors = Callable[[Agent], Iterable[Agent]]
Sensors = Callable[[Agent], Mapping[str, Any]]


class AggregateRuntime:
    """
    Runs an aggregate program on Mesa agents, in synchronous rounds or asynchronous spikes.

    In a synchronous round (the default), every agent receives what its neighbors sent in the
    previous round, so the result does not depend on the order of the agents. With
    ``synchronous=False``, each agent publishes its new message as soon as it runs, so the
    next agents to run already read it, and ``spike`` runs one agent at a time while keeping
    the state and messages of the others.

    Args:
        program: The ``@aggregate`` function to run on each agent.
        neighbors: The agents a given agent talks to, e.g. ``within(radius)`` in a
            continuous space or ``cell_neighbors`` in a grid.
        sensors: Extra sensors of a given agent, added to ``position`` (its position, or
            the coordinate of its cell) and ``time`` (the time of the model).
        synchronous: Whether ``run_round`` runs a synchronous round on all agents, or spikes
            them one after the other.
        retention: With ``synchronous=False``, for how long in ``model.time`` a silent agent
            is kept before its state, messages and outputs are forgotten; ``None`` by
            default, which keeps silent agents until ``forget`` or ``reset``.

    Raises:
        ValueError: If ``retention`` is given with ``synchronous=True``, or if ``retention``
            is not positive.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        program: Callable[[], Any],
        *,
        neighbors: Neighbors,
        sensors: Sensors | None = None,
        synchronous: bool = True,
        retention: float | None = None,
    ):
        if synchronous and retention is not None:
            raise ValueError("retention requires synchronous=False")
        self.neighbors = neighbors
        self.sensors = sensors
        self.synchronous = synchronous
        self._spikes = None if synchronous else AsynchronousRuntime(program, retention=retention)
        self._rounds = SynchronousRuntime(program) if self._spikes is None else self._spikes

    @property
    def program(self) -> Callable[[], Any]:
        """The ``@aggregate`` function run on each agent."""
        return self._rounds.program

    @program.setter
    def program(self, program: Callable[[], Any]) -> None:
        self._rounds.program = program

    @property
    def outputs(self) -> dict[int, dict[str, Any]]:
        """What the program stored with ``store`` on each agent, in the last round."""
        return self._rounds.outputs

    def run_round(self, agents: Iterable[Agent]) -> dict[int, Any]:
        """
        Run the program once on each of ``agents``.

        Agents missing from a round are forgotten: their state and messages are dropped.

        Args:
            agents: The agents of this round, e.g. ``model.agents``.

        Returns:
            The result of the program on each agent, by ``unique_id``.
        """
        agents = list(agents)
        sensors = {agent.unique_id: self._sense(agent) for agent in agents}
        neighbors = {
            agent.unique_id: [neighbor.unique_id for neighbor in self.neighbors(agent)]
            for agent in agents
        }
        return self._rounds.run_round(sensors, neighbors)

    def spike(self, agent: Agent) -> Any:
        """
        Run the program once on ``agent``, keeping the state and messages of the others.

        Args:
            agent: The agent running the spike.

        Returns:
            The result of the program on ``agent``.

        Raises:
            ValueError: If the runtime is synchronous.
        """
        neighbors = [neighbor.unique_id for neighbor in self.neighbors(agent)]
        return self._asynchronous("spike").spike(agent.unique_id, self._sense(agent), neighbors)

    def forget(self, agent: Agent | int) -> None:
        """
        Forget the state, the messages and the outputs of ``agent``.

        Args:
            agent: The agent to forget, or its ``unique_id``.

        Raises:
            ValueError: If the runtime is synchronous.
        """
        agent_id = agent.unique_id if isinstance(agent, Agent) else agent
        self._asynchronous("forget").forget(agent_id)

    def reset(self) -> None:
        """Forget the state and the messages of every agent."""
        self._rounds.reset()

    def _asynchronous(self, action: str) -> AsynchronousRuntime:
        """The underlying ``AsynchronousRuntime``, when ``synchronous=False``."""
        if self._spikes is None:
            raise ValueError(f"{action} requires synchronous=False")
        return self._spikes

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

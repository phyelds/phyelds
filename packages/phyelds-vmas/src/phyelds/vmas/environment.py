"""Adapter between VMAS environments and the phyelds simulator."""

from typing import Any, Callable, List

import vmas.simulator.environment

from phyelds.simulator import Environment, Node
from phyelds.vmas import devices


class VmasEnvironment(Environment):
    """Wrap a VMAS environment as a phyelds simulator environment."""

    def __init__(
        self,
        vmas_environment: vmas.simulator.environment.Environment,
        neighborhood_function: Callable[[Node, Environment], List[Node]] = None,
    ):
        super().__init__(neighborhood_function)
        self.vmas_environment = vmas_environment
        self.initialize_nodes()

    def initialize_nodes(self) -> None:
        """Create phyelds nodes from the agents in the VMAS environment."""
        observations = self.vmas_environment.reset()
        for index, agent in enumerate(self.vmas_environment.agents):
            data: dict[str, Any] = {
                devices.observations.name: observations[index][0],
                devices.rewards.name: 0.0,
                devices.dones.name: False,
                devices.infos.name: {},
                devices.agent.name: agent,
            }
            node = Node(
                position=(agent.state.pos[0][0].item(), agent.state.pos[0][1].item()),
                data=data,
                node_id=index,
            )
            self.add_node(node)

    def update_nodes(self, observations, rewards, dones, infos) -> None:
        """Synchronize phyelds nodes with the latest VMAS step result."""
        for index, agent in enumerate(self.vmas_environment.agents):
            node = self.nodes[index]
            node.data[devices.observations.name] = observations[index][0]
            node.position = (agent.state.pos[0][0].item(), agent.state.pos[0][1].item())
            node.data[devices.rewards.name] = rewards[index][0]
            node.data[devices.dones.name] = dones
            node.data[devices.infos.name] = infos[index]
            node.data[devices.agent.name] = agent

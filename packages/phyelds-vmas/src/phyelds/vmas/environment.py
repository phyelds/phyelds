"""Adapter between VMAS environments and the phyelds simulator."""

from typing import Any, Callable, List

import vmas.simulator.environment

from phyelds.simulator import Environment, Node


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
                "observations": observations[index][0],
                "rewards": 0.0,
                "dones": False,
                "infos": {},
                "agent": agent,
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
            node.data["observations"] = observations[index][0]
            node.position = (agent.state.pos[0][0].item(), agent.state.pos[0][1].item())
            node.data["rewards"] = rewards[index][0]
            node.data["dones"] = dones
            node.data["infos"] = infos[index]
            node.data["agent"] = agent

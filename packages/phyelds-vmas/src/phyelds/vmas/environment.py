"""Adapter between VMAS environments and the phyelds simulator."""

from collections.abc import Callable, Sequence
from typing import Any

from torch import Tensor
import vmas.simulator.environment

from phyelds.simulator import Environment, Node
from phyelds.vmas import devices


class VmasEnvironment(Environment):
    """Wrap VMAS agents as nodes with readings and positions from environment zero.

    Args:
        vmas_environment: The VMAS host, reset when the adapter is initialized.
        neighborhood_function: How to select each node's neighbors.
    """

    def __init__(
        self,
        vmas_environment: vmas.simulator.environment.Environment,
        neighborhood_function: Callable[[Node, Environment], list[Node]] | None = None,
    ) -> None:
        super().__init__(neighborhood_function)
        self.vmas_environment = vmas_environment
        self.initialize_nodes()

    def initialize_nodes(self) -> None:
        """Create phyelds nodes from the agents in the VMAS environment."""
        observations = self.vmas_environment.reset()
        for index, agent in enumerate(self.vmas_environment.agents):
            data: dict[str, Any] = {
                devices.observations.name: observations[index][0],
                devices.rewards.name: agent.state.pos.new_zeros(()),
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

    def update_nodes(
        self,
        observations: Sequence[Tensor],
        rewards: Sequence[Tensor],
        dones: Tensor,
        infos: Sequence[dict[str, Tensor]],
    ) -> None:
        """Synchronize nodes with environment zero of a batched VMAS step result.

        Args:
            observations: Batched observation tensors, one per agent.
            rewards: Batched reward tensors, one per agent.
            dones: Episode completion flags, one per environment.
            infos: Batched info tensors by name, one dictionary per agent.
        """
        for index, agent in enumerate(self.vmas_environment.agents):
            node = self.nodes[index]
            node.data[devices.observations.name] = observations[index][0]
            node.position = (agent.state.pos[0][0].item(), agent.state.pos[0][1].item())
            node.data[devices.rewards.name] = rewards[index][0]
            node.data[devices.dones.name] = bool(dones[0].item())
            node.data[devices.infos.name] = {
                name: value[0] for name, value in infos[index].items()
            }
            node.data[devices.agent.name] = agent

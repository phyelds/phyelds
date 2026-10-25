"""VMAS-specific simulation runner."""

import numpy as np
import torch

from phyelds.simulator import Simulator
from phyelds.vmas.environment import VmasEnvironment
from phyelds.vmas.devices import action


def vmas_runner(simulator: Simulator, time_delta: float) -> None:
    """Step VMAS from aggregate-program actions and schedule the next step.

    Args:
        simulator: The simulator wrapping the VMAS environment.
        time_delta: Delay before the next VMAS step.

    Raises:
        TypeError: If the simulator does not wrap a VMAS environment.
        ValueError: If a node has not sent an action, including before its first round.
    """
    if not isinstance(simulator.environment, VmasEnvironment):
        raise TypeError("vmas_runner requires a simulator with a VmasEnvironment")

    environment = simulator.environment
    actions = []
    for node in environment.node_list():
        value = action.read(node.data.get("outputs", {}))
        if value is None:
            raise ValueError(f"node {node.id} has no action; send it with action.send(...)")
        actions.append(np.array(value, dtype=np.float32))
    actions_single_env = torch.tensor(
        np.stack(actions), device=environment.vmas_environment.device
    )
    actions_batch = actions_single_env.expand(
        environment.vmas_environment.num_envs, -1, -1
    )
    actions_per_agent = list(actions_batch.unbind(dim=1))
    observations, rewards, dones, infos = environment.vmas_environment.step(actions_per_agent)
    environment.update_nodes(observations, rewards, dones, infos)
    simulator.schedule_event(time_delta, vmas_runner, simulator, time_delta)

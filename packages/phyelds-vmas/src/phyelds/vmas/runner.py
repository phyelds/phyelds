"""VMAS-specific simulation runner."""

import numpy as np
import torch

from phyelds.simulator import Simulator
from phyelds.vmas.environment import VmasEnvironment


def vmas_runner(simulator: Simulator, time_delta: float) -> None:
    """Step VMAS from aggregate-program actions and schedule the next step."""
    if not isinstance(simulator.environment, VmasEnvironment):
        raise TypeError("vmas_runner requires a simulator with a VmasEnvironment")

    environment = simulator.environment
    actions = [
        np.array(node.data["outputs"]["action"], dtype=np.float32)
        for node in environment.node_list()
    ]
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

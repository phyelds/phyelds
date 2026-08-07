import torch
from vmas import make_env

from phyelds.vmas import VmasEnvironment


def test_initializes_nodes_from_vmas_agents():
    environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1))

    assert list(environment.nodes) == list(range(len(environment.vmas_environment.agents)))
    for index, agent in enumerate(environment.vmas_environment.agents):
        node = environment.nodes[index]
        assert node.data["agent"] is agent
        assert node.data["rewards"] == 0.0
        assert node.data["dones"] is False
        assert node.position == (
            agent.state.pos[0][0].item(),
            agent.state.pos[0][1].item(),
        )


def test_updates_nodes_from_a_vmas_step():
    environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1))
    actions = [
        torch.zeros((1, 2), device=environment.vmas_environment.device)
        for _ in environment.vmas_environment.agents
    ]
    observations, rewards, dones, infos = environment.vmas_environment.step(actions)

    environment.update_nodes(observations, rewards, dones, infos)

    for index, agent in enumerate(environment.vmas_environment.agents):
        node = environment.nodes[index]
        assert torch.equal(node.data["observations"], observations[index][0])
        assert torch.equal(node.data["rewards"], rewards[index][0])
        assert node.data["dones"] is dones
        assert node.data["infos"] is infos[index]
        assert node.position == (
            agent.state.pos[0][0].item(),
            agent.state.pos[0][1].item(),
        )

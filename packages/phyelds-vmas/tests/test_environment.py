import pytest
import torch
from vmas import make_env

from phyelds.vmas import VmasEnvironment


@pytest.mark.parametrize("stepped", [False, True])
def test_sensor_values_keep_types_and_select_one_environment(stepped):
    environment = VmasEnvironment(make_env(scenario="flocking", num_envs=2, seed=0))
    if stepped:
        actions = [torch.zeros((2, 2)) for _ in environment.vmas_environment.agents]
        observations, rewards, _, _ = environment.vmas_environment.step(actions)
        infos = [
            {"metric": torch.tensor([[index, 10], [index + 100, 20]])}
            for index in environment.nodes
        ]
        environment.update_nodes(observations, rewards, torch.tensor([True, False]), infos)

    for index, node in environment.nodes.items():
        assert isinstance(node.data["observations"], torch.Tensor)
        assert isinstance(node.data["rewards"], torch.Tensor)
        assert node.data["rewards"].ndim == 0
        assert node.data["rewards"].device == node.data["observations"].device
        assert isinstance(node.data["dones"], bool)
        assert isinstance(node.data["infos"], dict)
        if stepped:
            assert torch.equal(node.data["observations"], observations[index][0])
            assert torch.equal(node.data["rewards"], rewards[index][0])
            assert node.data["dones"] is True
            assert torch.equal(node.data["infos"]["metric"], torch.tensor([index, 10]))
        else:
            assert node.data["rewards"].item() == 0.0
            assert node.data["dones"] is False
            assert node.data["infos"] == {}


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
        assert node.data["dones"] is bool(dones[0].item())
        assert node.data["infos"].keys() == infos[index].keys()
        for name, value in infos[index].items():
            assert torch.equal(node.data["infos"][name], value[0])
        assert node.position == (
            agent.state.pos[0][0].item(),
            agent.state.pos[0][1].item(),
        )

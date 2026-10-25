import pytest
from vmas import make_env

import phyelds.vmas as devices
from phyelds.calculus import aggregate
from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, vmas_runner


@pytest.mark.parametrize("run_program", [False, True])
def test_vmas_runner_names_node_when_action_is_missing(run_program):
    environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1, seed=0))
    simulator = Simulator(environment)

    @aggregate
    def send_nothing():
        return devices.observations.sense()

    if run_program:
        schedule_program_for_all(simulator, 0.0, 1.0, send_nothing)
    simulator.schedule_event(0.2, vmas_runner, simulator, 1.0)

    with pytest.raises(ValueError, match=r"node 0.*action"):
        simulator.run(1)


def test_vmas_runner_moves_agents_from_typed_sensors_and_action():
    environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1, seed=0))
    simulator = Simulator(environment)
    positions = [node.position for node in environment.node_list()]
    readings = {}

    @aggregate
    def move_right():
        current_agent = devices.agent.sense()
        readings[current_agent.name] = (
            devices.observations.sense(), devices.rewards.sense(),
            devices.dones.sense(), devices.infos.sense(),
        )
        devices.action.send([1, 0])

    schedule_program_for_all(simulator, 0.0, 2.0, move_right)
    simulator.schedule_event(0.2, vmas_runner, simulator, 1.0)
    simulator.run(1)

    for index, node in enumerate(environment.node_list()):
        assert node.position[0] > positions[index][0]
        assert node.position[1] == positions[index][1]
        values = readings[node.data["agent"].name]
        assert values[0].ndim == 1
        assert values[1] == 0.0
        assert values[2] is False
        assert values[3] == {}


def test_vmas_runner_moves_agents_from_aggregate_actions():
    vmas_environment = VmasEnvironment(
        make_env(
            scenario="flocking",
            num_envs=1,
        )
    )
    simulator = Simulator(vmas_environment)
    positions = [agent.state.pos.clone() for agent in vmas_environment.vmas_environment.agents]

    @aggregate
    def action():
        store("action", [1, 0])

    schedule_program_for_all(simulator, 0.0, 1.0, action)
    simulator.schedule_event(0.2, vmas_runner, simulator, 1.0)
    simulator.run(1)

    for index, agent in enumerate(vmas_environment.vmas_environment.agents):
        assert agent.state.pos[0][0].item() > positions[index][0][0].item()
        assert agent.state.pos[0][1].item() == positions[index][0][1].item()

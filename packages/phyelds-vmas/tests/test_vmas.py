from vmas import make_env

from phyelds.calculus import aggregate
from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, vmas_runner


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

from vmas import make_env

from phyelds.calculus import aggregate
from phyelds.libraries.device import store
from phyelds.simulator import Simulator, VmasEnvironment
from phyelds.simulator.runner import vmas_runner, schedule_program_for_all


def test_cancels_raise_error_if_event_not_found():
    vmas_environment = VmasEnvironment(
        make_env(
            scenario="flocking",
            num_envs=1,
        )
    )
    sim = Simulator(vmas_environment)
    # take agents positions
    positions = [agent.state.pos for agent in vmas_environment.vmas_environment.agents]
    @aggregate
    def action():
        store("action", [1, 0])

    schedule_program_for_all(sim, 0.0, 1.0, action)
    sim.schedule_event(
        0.2, vmas_runner, sim, 1.0
    )
    sim.run(1)
    # assert that all agents have moved in x direction
    for i, agent in enumerate(vmas_environment.vmas_environment.agents):
        assert agent.state.pos[0][0].item() > positions[i][0][0].item()
        assert agent.state.pos[0][1] == positions[i][0][1].item()



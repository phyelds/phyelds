"""
phyelds-mesa and a loop of ``Device``s, on the same agents and with synchronous rounds,
compute the same results in each round.
"""
import mesa
from mesa.discrete_space import CellAgent, OrthogonalMooreGrid

from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.mesa import AggregateRuntime, cell_neighbors
from phyelds.vm.device import Device

ROUNDS = 12


@aggregate
def gradient_leader_count():
    potential = distance_to(sense("source"))
    return potential.value, gossip_max(local_id()).value, count_nodes(potential).value


def _grid() -> list[CellAgent]:
    """One agent in each cell of a 4×3 grid, which reaches the 8 cells around it."""
    model = mesa.Model(rng=42)
    grid = OrthogonalMooreGrid((4, 3), torus=False, random=model.random)
    agents = []
    for cell in grid.all_cells:
        agent = CellAgent(model)
        agent.cell = cell
        agents.append(agent)
    return agents


def _sensors(agent: CellAgent) -> dict[str, bool]:
    return {"source": agent.cell.coordinate == (0, 0)}


def _runtime_rounds(agents: list[CellAgent]) -> list[dict]:
    runtime = AggregateRuntime(gradient_leader_count, neighbors=cell_neighbors, sensors=_sensors)
    return [runtime.run_round(agents) for _ in range(ROUNDS)]


def _device_rounds(agents: list[CellAgent]) -> list[dict]:
    """The same rounds on Devices: all of them run, then all of them send."""
    devices = {agent.unique_id: Device(agent.unique_id, gradient_leader_count) for agent in agents}
    rounds = []
    for _ in range(ROUNDS):
        sent = {agent.unique_id: devices[agent.unique_id].run_round(_sensors(agent)) for agent in agents}
        for agent in agents:
            for neighbor in cell_neighbors(agent):
                devices[neighbor.unique_id].receive(agent.unique_id, sent[agent.unique_id])
        rounds.append({agent_id: device.result for agent_id, device in devices.items()})
    return rounds


def test_runtime_computes_the_rounds_of_devices_on_the_same_agents():
    agents = _grid()

    expected = _device_rounds(agents)
    actual = _runtime_rounds(agents)

    assert actual == expected

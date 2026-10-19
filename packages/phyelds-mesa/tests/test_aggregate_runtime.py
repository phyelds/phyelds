import math

import mesa
from mesa.discrete_space import CellAgent, OrthogonalVonNeumannGrid
from mesa.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent

from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import local_position, sense, store
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time
from phyelds.mesa import AggregateRuntime, cell_neighbors, within


@aggregate
def hops_to_source():
    return distance_to(sense("source"), hops_distance())


@aggregate
def rounds():
    set_count, count = remember(0)
    return set_count(count + 1)


@aggregate
def position_and_time():
    return local_position(), local_time()


@aggregate
def neighbour_count():
    count = neighbors(1).sum(include_self=False)
    store("neighbours", count)
    return count


def _line(size: int) -> tuple[mesa.Model, list[ContinuousSpaceAgent]]:
    """Agents at x = 0, 1, 2, ...: each one reaches only the next and the previous."""
    model = mesa.Model(rng=42)
    space = ContinuousSpace([[0, size], [0, 1]], torus=False, random=model.random, n_agents=size)
    agents = []
    for x in range(size):
        agent = ContinuousSpaceAgent(space, model)
        agent.position = [float(x), 0.5]
        agents.append(agent)
    return model, agents


def _source_is(agent_id: int):
    return lambda agent: {"source": agent.unique_id == agent_id}


def _run(runtime: AggregateRuntime, agents, rounds_to_run: int) -> list:
    for _ in range(rounds_to_run):
        results = runtime.run_round(agents)
    return [results[agent.unique_id] for agent in agents]


def test_runtime_computes_a_gradient_on_agents_in_continuous_space():
    _, agents = _line(4)
    runtime = AggregateRuntime(hops_to_source, neighbors=within(1.5), sensors=_source_is(agents[0].unique_id))

    assert _run(runtime, agents, rounds_to_run=5) == [0.0, 1.0, 2.0, 3.0]


def test_runtime_rounds_are_synchronous_whatever_the_order_of_the_agents():
    _, agents = _line(4)
    runtime = AggregateRuntime(hops_to_source, neighbors=within(1.5), sensors=_source_is(agents[0].unique_id))

    first_round = runtime.run_round(agents)

    # Each agent sees what its neighbours sent in the previous round: nothing yet.
    assert [first_round[agent.unique_id] for agent in agents] == [0.0, math.inf, math.inf, math.inf]


def test_runtime_computes_a_gradient_on_agents_in_a_grid():
    model = mesa.Model(rng=42)
    grid = OrthogonalVonNeumannGrid((1, 4), torus=False, random=model.random)
    agents = []
    for column in range(4):
        agent = CellAgent(model)
        agent.cell = grid[(0, column)]
        agents.append(agent)
    runtime = AggregateRuntime(hops_to_source, neighbors=cell_neighbors, sensors=_source_is(agents[0].unique_id))

    assert _run(runtime, agents, rounds_to_run=5) == [0.0, 1.0, 2.0, 3.0]


def test_cell_neighbors_include_the_other_agents_in_the_same_cell():
    model = mesa.Model(rng=42)
    grid = OrthogonalVonNeumannGrid((2, 2), torus=False, random=model.random)
    first, second = CellAgent(model), CellAgent(model)
    first.cell = second.cell = grid[(0, 0)]

    assert list(cell_neighbors(first)) == [second]


def test_runtime_senses_the_position_of_the_agent_and_the_time_of_the_model():
    model, agents = _line(2)
    runtime = AggregateRuntime(position_and_time, neighbors=within(1.5))
    model.step()

    results = runtime.run_round(agents)

    assert results[agents[1].unique_id] == ((1.0, 0.5), 1.0)


def test_runtime_senses_the_coordinate_of_the_cell_of_an_agent():
    model = mesa.Model(rng=42)
    grid = OrthogonalVonNeumannGrid((3, 3), torus=False, random=model.random)
    agent = CellAgent(model)
    agent.cell = grid[(2, 1)]
    runtime = AggregateRuntime(position_and_time, neighbors=cell_neighbors)

    assert runtime.run_round([agent])[agent.unique_id] == ((2, 1), 0.0)


def test_runtime_exposes_what_the_program_stored():
    _, agents = _line(3)
    runtime = AggregateRuntime(neighbour_count, neighbors=within(1.5))

    _run(runtime, agents, rounds_to_run=2)

    assert [runtime.outputs[agent.unique_id]["neighbours"] for agent in agents] == [1, 2, 1]


def test_runtime_keeps_the_state_of_each_agent_across_rounds_until_reset():
    _, agents = _line(2)
    runtime = AggregateRuntime(rounds, neighbors=within(1.5))
    _run(runtime, agents, rounds_to_run=3)

    runtime.reset()

    assert _run(runtime, agents, rounds_to_run=1) == [1, 1]


def test_runtime_forgets_agents_that_left():
    model, agents = _line(3)
    runtime = AggregateRuntime(neighbour_count, neighbors=within(1.5))
    _run(runtime, agents, rounds_to_run=2)

    agents[2].remove()
    results = runtime.run_round(model.agents)

    assert agents[2].unique_id not in results
    assert results[agents[1].unique_id] == 1

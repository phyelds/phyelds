from phyelds.calculus import aggregate, neighbors, remember_and_evolve
from phyelds.simulator import Node
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import random_in_circle
from phyelds.simulator.neighborhood import full_neighborhood
from phyelds.simulator.runner import (
    aggregate_program_runner, schedule_program_for_all,
)


def test_aggregate_program_runner_with_plain_result(monkeypatch):
    # real Node & real Simulator
    sim = Simulator()
    node = sim.create_node((0, 0), node_id=1)
    # program that returns a bare value
    called = {}
    def program():
        called["ran"] = True
        return 42

    sim.schedule_event(0.5, aggregate_program_runner, sim, 0.5, node, program)
    sim.run(0.5)
    assert called["ran"] is True
    assert node.data["result"] == 42
    
def test_aggregate_program_runner_with_aggregate(monkeypatch):
    sim = Simulator()
    node = sim.create_node((0, 0), node_id=1)
    @aggregate
    def program():
        return remember_and_evolve(0, lambda x: x + 1)

    sim.schedule_event(0.5, aggregate_program_runner, sim, 0.5, node, program)
    sim.run(1) # 2 called
    assert node.data["result"] == 2

def test_aggregate_program_should_not_run_when_a_not_is_not_in_the_environment():
    sim = Simulator()
    node = Node((0.0, 0.0), node_id=1)
    sim.environment.add_node(node)

    @aggregate
    def program():
        return 42
    # Schedule the program
    schedule_program_for_all(sim, 1.0, program)
    # Remove the node from the environment
    sim.environment.remove_node(node.id)
    # Run the simulation
    sim.run(2)

    # Assert that the result is not set
    assert "result" not in node.data
def test_aggregate_program_with_neighbors():
    sim = Simulator()
    sim.environment.set_neighborhood_function(full_neighborhood)
    random_in_circle(sim, num_nodes=3, radius=3)

    @aggregate
    def program():
        others = neighbors(1)
        return sum(others)

    schedule_program_for_all(sim, 1.0, program)
    sim.run(10)  # 2 called
    node = sim.environment.nodes[0]
    assert node.data["result"] == 3

def test_aggregate_program_with_parameters():
    sim = Simulator()
    node = Node((0.0, 0.0), node_id=1)
    sim.environment.add_node(node)

    @aggregate
    def program(value):
        return value

    schedule_program_for_all(sim, 1.0, program, value=1)
    sim.run(2)
    assert node.data['result'] == 1

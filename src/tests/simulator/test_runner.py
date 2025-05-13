from phyelds.calculus import aggregate, remember, neighbors
from phyelds.simulator import Node
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import random_in_circle
from phyelds.simulator.neighborhood import full_neighborhood
from phyelds.simulator.runner import (
    aggregate_program_runner,
)

def test_aggregate_program_runner_with_plain_result(monkeypatch):
    # real Node & real Simulator
    node = Node(position=(1, 2), data={"state": {"prev": True}})
    sim = Simulator()
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
    node = Node(position=(0, 0), data={"state": {"a": 1}})
    sim = Simulator()
    @aggregate
    def program():
        return remember(0).update_fn(lambda x: x + 1)

    sim.schedule_event(0.5, aggregate_program_runner, sim, 0.5, node, program)
    sim.run(1) # 2 called
    assert node.data["result"] == 2

def test_aggregate_program_with_neighbors():
    sim = Simulator()
    sim.environment.set_neighborhood_function(full_neighborhood)
    random_in_circle(sim, num_nodes=3, radius=3)

    @aggregate
    def program():
        others = neighbors(1)
        return sum(others)

    for node in sim.environment.nodes:
        current_node = sim.environment.nodes[node]
        sim.schedule_event(0.5, aggregate_program_runner, sim, 0.5, current_node, program)
    sim.run(10)  # 2 called
    node = sim.environment.nodes[0]
    assert node.data["result"] == 3
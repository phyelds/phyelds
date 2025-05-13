from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import aggregate_program_runner


def test_distance_to_should_compute_the_multi_hop_distance_from_source():
    simulator = Simulator()
    size = 5
    # 0 - 1 - 2 - 3 - 4
    grid_generation(simulator, size, 1, spacing=1)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))
    source = simulator.environment.nodes[0]
    for node in simulator.environment.nodes.values():
        node.data["source"] = False
    source.data["source"] = True
    @aggregate
    def program():
        return distance_to(sense("source"), hops_distance())
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(1, aggregate_program_runner, simulator, 1, node, program)
    simulator.run(10.0)
    # last node: size - 1 should be far 4 steps from the source
    assert simulator.environment.nodes[size - 1].data["result"] == (size - 1)



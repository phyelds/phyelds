from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to, cast_from, broadcast
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator

ITERATIONS = 10

def test_distance_to_should_compute_the_multi_hop_distance_from_source():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        return distance_to(sense("source"), hops_distance())
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # last node: size - 1 should be far 4 steps from the source
    assert simulator.environment.nodes[size - 1].data["result"] == (size - 1)

def test_broadcast_cast_multi_hop():
    size = 5
    simulator = setup_up_simulator(size)
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        return broadcast(sense("source"), local_id(), hops_distance())
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # for all node, result should be 0
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == 0

def test_cast_should_accumulate_over_the_path():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        return cast_from(sense("source"), 'a', lambda a: a + 'a', hops_distance())
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    for i in range(size):
        assert simulator.environment.nodes[i].data["result"] == 'a' * (i + 1)

import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.collect import collect_with, count_nodes, sum_values, collect_or
from phyelds.libraries.device import sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator


def test_collect_should_collect_data_towards_the_center():
    simulator = setup_up_simulator(5)
    # 0 - 1 - 2 - 3 - 4
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        potential = distance_to(sense("source"), hops_distance())
        return collect_with(potential, 1, lambda a, b: a + b)
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(10)
    assert simulator.environment.nodes[0].data["result"] == 5

def test_sum_values_should_sum_value_over_the_path():
    simulator = setup_up_simulator(5)
    # 0 - 1 - 2 - 3 - 4
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        potential = distance_to(sense("source"), hops_distance())
        return sum_values(potential, 10)
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(10)
    assert simulator.environment.nodes[0].data["result"] == 50

@pytest.mark.parametrize("size", [5, 10, 20])
def test_count_node_should_return_the_right_number_of_nodes(size):
    simulator = setup_up_simulator(size)
    # 0 - 1 - 2 - 3 - 4
    source = simulator.environment.nodes[0]
    source.update(new_data={"source": True})
    @aggregate
    def program():
        potential = distance_to(sense("source"), hops_distance())
        return count_nodes(potential)
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(size * size)
    assert simulator.environment.nodes[0].data["result"] == size

def test_collect_or_should_create_a_path_between_two_zone():
    simulator = setup_up_simulator(5, 5)
    source = simulator.environment.nodes[0]
    target = simulator.environment.nodes[4]
    source.data["source"] = True
    target.data["target"] = True
    @aggregate
    def program():
        potential = distance_to(sense("source"), hops_distance())
        return collect_or(potential, sense("target"))
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(10)
    # 0 1 2 3 4 true, the other false
    for i in range(5):
        assert simulator.environment.nodes[i].data["result"] == True
    for i in range(5, len(simulator.environment.nodes)):
        assert simulator.environment.nodes[i].data["result"] == False
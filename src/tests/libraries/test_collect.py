import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.collect import (
    broadcast_collect,
    collect_or,
    collect_with,
    count_nodes,
    find_parents,
    mean_values,
    multi_path,
    point_to_point,
    sum_values,
    summarize,
)
from phyelds.libraries.device import local_id, sense
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    # 0 1 2 3 4 true, the other false
    for i in range(5):
        assert simulator.environment.nodes[i].data["result"] == True
    for i in range(5, len(simulator.environment.nodes)):
        assert simulator.environment.nodes[i].data["result"] == False


def test_find_parents_returns_all_neighbors_with_smaller_potential():
    # 2x2 grid: 0=(0,0), 1=(0,1), 2=(1,0), 3=(1,1) with radius 1.1
    # From source 0: potential(0)=0, potential(1)=1, potential(2)=1, potential(3)=2
    # Node 3 has both 1 and 2 at lower potential (1 < 2)
    simulator = setup_up_simulator(2, 2)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def program():
        potential = distance_to(sense("source"), hops_distance())
        return find_parents(potential)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(6)
    assert simulator.environment.nodes[0].data["result"] == set()
    assert simulator.environment.nodes[1].data["result"] == {0}
    assert simulator.environment.nodes[2].data["result"] == {0}
    assert simulator.environment.nodes[3].data["result"] == {1, 2}


def test_point_to_point_collect_and_mean_values_accumulate_accurately():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def program():
        potential = distance_to(sense("source"))
        total = sum_values(potential, local_id() * 10, strategy=point_to_point())
        avg = mean_values(potential, float(local_id() * 10), strategy=point_to_point())
        avg_broadcast = mean_values(potential, float(local_id() * 10), strategy=broadcast_collect())
        return total, avg, avg_broadcast

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(12)
    # Values are 0, 10, 20, 30, 40 -> sum = 100, mean = 20.0
    assert simulator.environment.nodes[0].data["result"] == (100, 20.0, 20.0)


def test_summarize_collects_and_broadcasts_total_across_all_nodes():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[2].data["source"] = True

    @aggregate
    def program():
        return summarize(
            sense("source"),
            10,
            lambda a, b: a + b,
            collect_strategy=point_to_point(),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(12)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == 50


def test_multi_path_collect_splits_contributions_across_all_parents_in_dag():
    # 2x2 grid: node 3 has two parents (1 and 2) at potential 1.
    # Node 3 splits its 10.0 equally (5.0 to node 1, 5.0 to node 2).
    simulator = setup_up_simulator(2, 2)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def program():
        potential = distance_to(sense("source"))
        return sum_values(potential, 10.0, strategy=multi_path())

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(8)
    assert simulator.environment.nodes[3].data["result"] == 10.0
    assert simulator.environment.nodes[1].data["result"] == 15.0
    assert simulator.environment.nodes[2].data["result"] == 15.0
    assert simulator.environment.nodes[0].data["result"] == 40.0



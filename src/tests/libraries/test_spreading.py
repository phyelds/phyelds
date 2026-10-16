import math
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, local_id, local_position
from phyelds.libraries.distances import hops_distance, neighbors_distances
from phyelds.libraries.spreading import (
    distance_to,
    cast_from,
    broadcast,
    bellman_ford,
    path_coherent,
)
from phyelds.simulator import Simulator
from phyelds.simulator.neighborhood import radius_neighborhood
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    for i in range(size):
        assert simulator.environment.nodes[i].data["result"] == 'a' * (i + 1)


def test_spreading_functions_default_to_hops_distance_when_distances_omitted():
    size = 4
    simulator = setup_up_simulator(size)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def program():
        return (
            distance_to(sense("source")),
            broadcast(sense("source"), local_id()),
            cast_from(sense("source"), 0, lambda d: d + 10),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    for i in range(size):
        assert simulator.environment.nodes[i].data["result"] == (i, 0, i * 10)


def test_path_coherent_strategy_avoids_rising_value_problem():
    simulator = Simulator()
    left = -1e-4
    right = 1e-4
    simulator.create_node((0.0, 0.0), data={"source": True}, node_id=0)
    simulator.create_node((1.0, left), data={"source": False}, node_id=1)
    simulator.create_node((1.0, right), data={"source": False}, node_id=2)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))

    @aggregate
    def program():
        y_coord = local_position()[1]
        return (
            broadcast(
                sense("source"),
                y_coord,
                neighbors_distances(),
                strategy=path_coherent(),
            ),
            broadcast(
                sense("source"),
                y_coord,
                neighbors_distances(),
                strategy=bellman_ford(),
            ),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(3)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (0.0, 0.0)

    # Remove the source: path_coherent recovers in a couple of rounds,
    # whereas bellman_ford stays trapped in the 1 <-> 2 cycle for thousands of rounds.
    simulator.environment.remove_node(0)
    simulator.continue_run(4)
    assert simulator.environment.nodes[1].data["result"][0] == left
    assert simulator.environment.nodes[2].data["result"][0] == right
    assert simulator.environment.nodes[1].data["result"][1] == 0.0
    assert simulator.environment.nodes[2].data["result"][1] == 0.0


def test_path_coherent_respects_max_diameter_and_three_arg_accumulation():
    size = 5
    simulator = setup_up_simulator(size)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def program():
        dist = distance_to(sense("source"), strategy=path_coherent(max_diameter=2))
        accumulated = cast_from(
            sense("source"),
            0.0,
            lambda from_src, edge, data: data + from_src + edge,
            strategy=path_coherent(max_diameter=2),
        )
        return dist, accumulated

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    assert simulator.environment.nodes[0].data["result"] == (0.0, 0.0)
    assert simulator.environment.nodes[1].data["result"] == (1.0, 1.0)
    assert simulator.environment.nodes[2].data["result"] == (2.0, 3.0)
    assert math.isinf(simulator.environment.nodes[3].data["result"][0])
    assert simulator.environment.nodes[3].data["result"][1] == 0.0


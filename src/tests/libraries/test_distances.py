from phyelds.calculus import aggregate
from phyelds.libraries.device import local_position
from phyelds.libraries.distances import hops_distance, neighbors_distances
from phyelds.simulator.neighborhood import full_neighborhood
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all


def test_hop_distances_should_return_correct_distance():
    simulator = Simulator()
    # Create two nodes with known positions
    grid_generation(simulator, 3, 3, 1.0)
    simulator.environment.set_neighborhood_function(full_neighborhood)
    @aggregate
    def program():
        return hops_distance().data
    # Act
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    # Assert
    for node in simulator.environment.nodes.values():
        # The distance to itself should be 0
        assert node.data["result"][node.id] == 0
        # The distance to the neighbors should be 1
        for neighbor_id in simulator.environment.get_neighbors(node):
            assert node.data["result"][neighbor_id.id] == 1

def test_distance_should_return_correct_distance():
    simulator = Simulator()
    # Create three nodes
    node_a = simulator.create_node((2, 0), node_id=0)
    node_b = simulator.create_node((0, 0), node_id=1)
    node_c = simulator.create_node((0, -2), node_id=2)
    simulator.environment.set_neighborhood_function(full_neighborhood)
    @aggregate
    def program():
        return neighbors_distances().data
    # Act
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    # assert the distance form 1 to 0
    assert node_b.data["result"][node_b.id] == 0
    # assert the distance form 2 to 0
    assert node_a.data["result"][node_b.id] == 2
    # assert the distance form 1 to 2
    assert node_c.data["result"][node_b.id] == 2


def test_neighbors_distances_supports_3d_and_custom_positions():
    simulator = Simulator()
    node_a = simulator.create_node((0.0, 0.0, 0.0), node_id=0)
    node_b = simulator.create_node((3.0, 4.0, 12.0), node_id=1)
    simulator.environment.set_neighborhood_function(full_neighborhood)

    @aggregate
    def program():
        return (
            neighbors_distances().data,
            neighbors_distances((0.0, 5.0 * local_position()[0])).data,
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(3)
    dist_3d, dist_custom = node_a.data["result"]
    assert dist_3d[0] == 0.0
    assert dist_3d[1] == 13.0
    assert dist_custom[1] == 15.0


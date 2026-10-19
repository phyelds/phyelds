from phyelds.simulator import Environment, Node
from phyelds.simulator.neighborhood import (
    radius_neighborhood,
    k_nearest_neighbors,
    full_neighborhood
)


def test_radius_neighborhood_includes_nodes_within_radius():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(0.5, 0))  # distance = 0.5
    node3 = Node(node_id=3, position=(1.5, 0))  # distance = 1.5
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)
    env.add_node(node3)

    neighbors = radius_neighborhood(1.0)(node1, env)

    assert len(neighbors) == 1
    assert node2 in neighbors
    assert node3 not in neighbors


def test_radius_neighborhood_with_zero_radius():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(0.1, 0))
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)

    neighbors = radius_neighborhood(0)(node1, env)

    assert len(neighbors) == 0


def test_radius_neighborhood_with_no_other_nodes():
    node = Node(node_id=1, position=(0, 0))
    env = Environment()
    env.add_node(node)

    neighbors = radius_neighborhood(1.0)(node, env)

    assert len(neighbors) == 0


def test_k_nearest_neighbors_returns_k_closest_nodes():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    node3 = Node(node_id=3, position=(2, 0))
    node4 = Node(node_id=4, position=(3, 0))
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)
    env.add_node(node3)
    env.add_node(node4)

    neighbors = k_nearest_neighbors(2)(node1, env)

    assert len(neighbors) == 2
    assert node2 in neighbors
    assert node3 in neighbors
    assert node4 not in neighbors


def test_k_nearest_neighbors_with_zero_k():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)

    neighbors = k_nearest_neighbors(0)(node1, env)

    assert len(neighbors) == 0


def test_k_nearest_neighbors_with_k_greater_than_nodes():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)
    neighbors = k_nearest_neighbors(5)(node1, env)

    assert len(neighbors) == 1
    assert node2 in neighbors


def test_full_neighborhood_returns_all_except_self():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    node3 = Node(node_id=3, position=(2, 0))
    env = Environment()
    env.add_node(node1)
    env.add_node(node2)
    env.add_node(node3)

    neighbors = full_neighborhood(node1, env)

    assert len(neighbors) == 2
    assert node2 in neighbors
    assert node3 in neighbors
    assert node1 not in neighbors


def test_full_neighborhood_with_no_other_nodes():
    node = Node(node_id=1, position=(0, 0))
    env = Environment()
    env.add_node(node)

    neighbors = full_neighborhood(node, env)

    assert len(neighbors) == 0

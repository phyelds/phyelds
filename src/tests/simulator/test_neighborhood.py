from phyelds.simulator import Node
from phyelds.simulator.neighborhood import (
    radius_neighborhood,
    k_nearest_neighbors,
    full_neighborhood
)


def test_radius_neighborhood_includes_nodes_within_radius():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(0.5, 0))  # distance = 0.5
    node3 = Node(node_id=3, position=(1.5, 0))  # distance = 1.5
    all_nodes = [node1, node2, node3]

    neighbors = radius_neighborhood(1.0)(node1, all_nodes)

    assert len(neighbors) == 1
    assert node2 in neighbors
    assert node3 not in neighbors


def test_radius_neighborhood_with_zero_radius():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(0.1, 0))
    all_nodes = [node1, node2]

    neighbors = radius_neighborhood(0)(node1, all_nodes)

    assert len(neighbors) == 0


def test_radius_neighborhood_with_no_other_nodes():
    node = Node(node_id=1, position=(0, 0))

    neighbors = radius_neighborhood(1.0)(node, [node])

    assert len(neighbors) == 0


def test_k_nearest_neighbors_returns_k_closest_nodes():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    node3 = Node(node_id=3, position=(2, 0))
    node4 = Node(node_id=4, position=(3, 0))
    all_nodes = [node1, node2, node3, node4]

    neighbors = k_nearest_neighbors(2)(node1, all_nodes)

    assert len(neighbors) == 2
    assert node2 in neighbors
    assert node3 in neighbors
    assert node4 not in neighbors


def test_k_nearest_neighbors_with_zero_k():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    all_nodes = [node1, node2]

    neighbors = k_nearest_neighbors(0)(node1, all_nodes)

    assert len(neighbors) == 0


def test_k_nearest_neighbors_with_k_greater_than_nodes():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    all_nodes = [node1, node2]

    neighbors = k_nearest_neighbors(5)(node1, all_nodes)

    assert len(neighbors) == 1
    assert node2 in neighbors


def test_full_neighborhood_returns_all_except_self():
    node1 = Node(node_id=1, position=(0, 0))
    node2 = Node(node_id=2, position=(1, 0))
    node3 = Node(node_id=3, position=(2, 0))
    all_nodes = [node1, node2, node3]

    neighbors = full_neighborhood(node1, all_nodes)

    assert len(neighbors) == 2
    assert node2 in neighbors
    assert node3 in neighbors
    assert node1 not in neighbors


def test_full_neighborhood_with_no_other_nodes():
    node = Node(node_id=1, position=(0, 0))

    neighbors = full_neighborhood(node, [node])

    assert len(neighbors) == 0

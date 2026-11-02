import math
import random

import pytest

from phyelds.calculus import neighbors
from phyelds.simulator import Environment, Node, Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.simulator.neighborhood import (
    radius_neighborhood,
    k_nearest_neighbors,
    full_neighborhood,
    adaptive_range,
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


def _rounds(environment, neighborhood, rounds):
    """Let every node compute its neighbors once per round, as the runner does."""
    for time in range(rounds):
        for node in environment.node_list():
            node.data["time"] = float(time)
            neighborhood(node, environment)


def _line(count, spacing):
    environment = Environment()
    for node_id in range(count):
        environment.add_node(Node(node_id=node_id, position=(node_id * spacing, 0.0)))
    return environment


def test_adaptive_range_shrinks_in_a_crowd_until_few_enough_neighbors():
    environment = _line(30, 0.1)
    neighborhood = adaptive_range(3.0, neighbors=4, tolerance=1, step=0.1, min_range=0.05)

    _rounds(environment, neighborhood, 40)

    middle = environment.nodes[15]
    assert len(neighborhood(middle, environment)) <= 5
    assert neighborhood.range_of(middle) < 3.0


def test_adaptive_range_grows_when_alone_until_enough_neighbors():
    environment = _line(10, 2.0)
    neighborhood = adaptive_range(1.0, neighbors=2, tolerance=0, step=0.5)

    _rounds(environment, neighborhood, 10)

    assert len(neighborhood(environment.nodes[5], environment)) >= 2


def test_adaptive_range_stays_within_its_bounds():
    environment = _line(3, 50.0)
    neighborhood = adaptive_range(1.0, neighbors=2, tolerance=0, min_range=0.5, max_range=4.0)

    _rounds(environment, neighborhood, 20)

    assert neighborhood.range_of(environment.nodes[1]) == 4.0
    assert neighborhood(environment.nodes[1], environment) == []


def test_adaptive_range_links_only_nodes_in_range_of_each_other():
    environment = _line(2, 2.0)
    neighborhood = adaptive_range(1.0, neighbors=1, tolerance=0)
    first, second = environment.nodes[0], environment.nodes[1]
    neighborhood.ranges[first.id] = 3.0

    assert neighborhood(first, environment) == []
    neighborhood.ranges[second.id] = 3.0
    assert neighborhood(first, environment) == [second]


def test_adaptive_range_adapts_once_per_round_of_the_node():
    environment = _line(2, 5.0)
    neighborhood = adaptive_range(1.0, neighbors=1, tolerance=0)
    node = environment.nodes[0]

    for _ in range(3):  # a renderer drawing the edges, within one round
        neighborhood(node, environment)

    assert neighborhood.range_of(node) == 2.0


def test_adaptive_range_keeps_a_crowd_running_a_program_to_few_neighbors():
    simulator = Simulator()
    for node_id in range(25):
        row, column = divmod(node_id, 5)
        simulator.create_node((column * 0.2, row * 0.2), node_id=node_id)
    neighborhood = adaptive_range(2.0, neighbors=6, tolerance=2, step=0.1, min_range=0.1)
    simulator.environment.set_neighborhood_function(neighborhood)
    schedule_program_for_all(simulator, 0.0, 1.0, lambda: neighbors(1).sum())

    simulator.run(30)

    counts = [node.data["result"] - 1 for node in simulator.environment.nodes.values()]
    assert max(counts) <= 8 and min(counts) >= 1


def _scanning_every_node(radius):
    """The neighbors as radius_neighborhood defines them: a scan of every node, in their order."""
    def neighborhood(node, environment):
        return [
            other for other in environment.node_list()
            if other.id != node.id
            and sum((a - b) ** 2 for a, b in zip(node.position, other.position)) ** 0.5 <= radius
        ]
    return neighborhood


def _assert_same_neighbors(neighborhood, environment, radius):
    reference = _scanning_every_node(radius)
    for node in environment.node_list():
        found = [other.id for other in neighborhood(node, environment)]
        assert found == [other.id for other in reference(node, environment)], node.id


def _scattered(environment, rng, count, dimensions, start=0):
    for node_id in range(start, start + count):
        position = tuple(round(rng.uniform(0, 10), 1) for _ in range(dimensions))
        environment.add_node(Node(position=position, node_id=node_id))


@pytest.mark.parametrize("dimensions", [2, 3])
@pytest.mark.parametrize("radius", [-1, 0, 0.1, 1, 2.5, math.inf])
def test_radius_neighborhood_finds_the_nodes_a_scan_of_every_node_finds(dimensions, radius):
    rng = random.Random(7)
    environment = Environment()
    _scattered(environment, rng, 150, dimensions)
    neighborhood = radius_neighborhood(radius)
    _assert_same_neighbors(neighborhood, environment, radius)

    for node in environment.node_list()[::2]:
        node.position = tuple(coordinate + rng.uniform(-3, 3) for coordinate in node.position)
    environment.nodes[1].update(new_position=environment.nodes[3].position)
    _assert_same_neighbors(neighborhood, environment, radius)

    for node_id in range(0, 150, 5):
        environment.remove_node(node_id)
    _scattered(environment, rng, 20, dimensions, start=150)
    _scattered(environment, rng, 3, dimensions, start=0)
    environment.add_node(Node(position=(5.0,) * dimensions, node_id=7))
    _assert_same_neighbors(neighborhood, environment, radius)

    environment.nodes[8].position = (math.nan,) * dimensions
    environment.nodes[9].position = (math.inf,) + (0.0,) * (dimensions - 1)
    _assert_same_neighbors(neighborhood, environment, radius)


def test_radius_neighborhood_compares_positions_of_different_dimensions_as_a_scan_does():
    environment = Environment()
    _scattered(environment, random.Random(3), 50, 2)
    environment.add_node(Node(position=(5.0, 5.0, 100.0), node_id="tall"))

    _assert_same_neighbors(radius_neighborhood(2.0), environment, 2.0)

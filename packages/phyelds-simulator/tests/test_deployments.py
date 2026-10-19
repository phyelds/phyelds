import pytest
from unittest.mock import Mock, MagicMock, call
import random
import math

from phyelds.simulator.deployments import grid_generation, deformed_lattice, random_walk, random_in_circle

from phyelds.simulator import Simulator, Node


@pytest.fixture
def simulator_mock():
    simulator = Mock(spec=Simulator)
    simulator.create_node = MagicMock()
    simulator.schedule_event = MagicMock()
    return simulator

@pytest.fixture
def node_mock():
    node = Mock(spec=Node)
    node.update = MagicMock()
    return node

def test_grid_generation_creates_correct_number_of_nodes(simulator_mock):
    # Arrange
    width, height, spacing = 3, 4, 10.0

    # Act
    grid_generation(simulator_mock, width, height, spacing)

    # Assert
    assert simulator_mock.create_node.call_count == width * height

def test_grid_generation_positions_nodes_correctly(simulator_mock):
    # Arrange
    width, height, spacing = 2, 2, 10.0
    expected_calls = [
        call((0.0, 0.0), node_id=0),
        call((0.0, 10.0), node_id=1),
        call((10.0, 0.0), node_id=2),
        call((10.0, 10.0), node_id=3)
    ]

    # Act
    grid_generation(simulator_mock, width, height, spacing)

    # Assert
    simulator_mock.create_node.assert_has_calls(expected_calls, any_order=True)

def test_grid_generation_with_zero_dimensions(simulator_mock):
    # Act
    grid_generation(simulator_mock, 0, 0, 10.0)

    # Assert
    simulator_mock.create_node.assert_not_called()

def test_deformed_lattice_creates_correct_number_of_nodes(simulator_mock):
    # Arrange
    width, height, spacing, deformation = 3, 4, 10.0, 2.0

    # Act
    deformed_lattice(simulator_mock, width, height, spacing, deformation)

    # Assert
    assert simulator_mock.create_node.call_count == width * height

def test_deformed_lattice_positions_nodes_within_bounds(simulator_mock):
    # Arrange
    width, height, spacing, deformation = 2, 2, 10.0, 2.0
    random.seed(42)  # Set seed for reproducibility

    # Act
    deformed_lattice(simulator_mock, width, height, spacing, deformation)

    # Assert
    for call_args in simulator_mock.create_node.call_args_list:
        pos = call_args[0][0]
        x, y = pos
        x_base = (call_args[1]['node_id'] // height) * spacing
        y_base = (call_args[1]['node_id'] % height) * spacing
        assert x_base - deformation <= x <= x_base + deformation
        assert y_base - deformation <= y <= y_base + deformation

def test_random_walk_creates_correct_number_of_nodes(simulator_mock):
    # Arrange
    num_steps, step_size = 10, 1.0

    # Act
    random_walk(simulator_mock, num_steps, step_size)

    # Assert
    assert simulator_mock.create_node.call_count == num_steps

def test_random_walk_position_updates_incrementally(simulator_mock):
    # Arrange
    random.seed(42)  # Set seed for reproducibility

    # Act
    random_walk(simulator_mock, 3, 1.0)

    # Assert
    calls = simulator_mock.create_node.call_args_list
    for i in range(1, len(calls)):
        prev_pos = calls[i - 1][0][0]
        curr_pos = calls[i][0][0]
        # Check that each position is derived from the previous one
        assert abs(curr_pos[0] - prev_pos[0]) <= 1.0
        assert abs(curr_pos[1] - prev_pos[1]) <= 1.0

def test_random_in_circle_creates_correct_number_of_nodes(simulator_mock):
    # Arrange
    num_nodes, radius = 10, 5.0

    # Act
    random_in_circle(simulator_mock, num_nodes, radius)

    # Assert
    assert simulator_mock.create_node.call_count == num_nodes

def test_random_in_circle_positions_nodes_within_radius(simulator_mock):
    # Arrange
    num_nodes, radius = 20, 5.0
    random.seed(42)  # Set seed for reproducibility

    # Act
    random_in_circle(simulator_mock, num_nodes, radius)

    # Assert
    for call_args in simulator_mock.create_node.call_args_list:
        pos = call_args[0][0]
        distance = math.sqrt(pos[0] ** 2 + pos[1] ** 2)
        assert distance <= radius


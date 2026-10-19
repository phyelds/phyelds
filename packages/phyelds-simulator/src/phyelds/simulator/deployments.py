"""
This module contains various functions to generate different types of node distributions
in a simulation environment.
These functions can be used to create specific patterns or random distributions of nodes
for testing and simulation purposes.
"""

import math
import random

from phyelds.simulator import Simulator


def grid_generation(simulator: Simulator, width: int, height: int, spacing: float):
    """
    Generate a grid of nodes in the simulator's environment.
    """
    for x in range(0, width):
        for y in range(0, height):
            position = (x * spacing, y * spacing)
            simulator.create_node(position, node_id=x * height + y)


def deformed_lattice(
    simulator: Simulator,
    width: int,
    height: int,
    spacing: float,
    deformation_factor: float,
):
    """
    Generate a deformed lattice of nodes in the simulator's environment.
    """
    for x in range(0, width):
        for y in range(0, height):
            # Randomly deform the position
            dx = random.uniform(-deformation_factor, deformation_factor)
            dy = random.uniform(-deformation_factor, deformation_factor)
            position = (x * spacing + dx, y * spacing + dy)
            simulator.create_node(position, node_id=x * height + y)


def random_walk(simulator: Simulator, num_steps: int, step_size: float):
    """
    Perform a random walk and create nodes at each step.
    """
    position = (0.0, 0.0)
    for _ in range(num_steps):
        dx = random.uniform(-step_size, step_size)
        dy = random.uniform(-step_size, step_size)
        position = (position[0] + dx, position[1] + dy)
        simulator.create_node(position)


def random_in_circle(simulator: Simulator, num_nodes: int, radius: float):
    """
    Generate nodes randomly distributed within a circle.
    """
    for index in range(num_nodes):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, radius)
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        simulator.create_node((x, y), node_id=index)

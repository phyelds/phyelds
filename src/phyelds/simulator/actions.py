"""
Sent of actions related to node movements and interactions in the simulator
"""
import random
from typing import Tuple

from phyelds.simulator import Simulator, Node


def move_with_velocity(
        simulator: Simulator, delta_time: float, node: Node, velocity: float
):
    """
    Move the node with a given velocity.
    """
    # Update the node's position based on its velocity and the delta time
    (x, y) = node.position
    (vx, vy) = velocity
    new_position = (x + vx * delta_time, y + vy * delta_time)
    node.update(new_position)
    simulator.schedule_event(
        delta_time, move_with_velocity, simulator, delta_time, node, velocity
    )


def gaussian_movement(
    simulator: Simulator, node: Node, mean: Tuple[float, ...], stddev: float
):
    """
    Move a node according to a Gaussian distribution.
    """
    new_position = tuple(random.gauss(mean[i], stddev) for i in range(len(mean)))
    node.update(new_position)
    # next schedule the event
    simulator.schedule_event(1.0, gaussian_movement, simulator, node, mean, stddev)

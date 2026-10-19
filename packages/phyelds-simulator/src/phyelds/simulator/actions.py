"""
Sent of actions related to node movements and interactions in the simulator
"""
import math
import random
from typing import Optional, Tuple

from phyelds.simulator import Simulator, Node


def move_with_velocity(
    simulator: Simulator,
    delta_time: float,
    node: Node,
    velocity: Tuple[float, tuple]
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


def follow_velocity(
    simulator: Simulator,
    delta_time: float,
    node: Node,
    output: str = "velocity",
    max_speed: Optional[float] = None,
):
    """
    Move a node, every ``delta_time``, by the velocity its program stores.

    The velocity is what the program stores as ``output`` (``store("velocity", v)``), with
    as many components as the position or more: a planar node ignores a height. A node
    whose program has stored nothing yet stays still.

    Args:
        simulator: The simulator.
        delta_time: The time between two moves, and the time each move lasts.
        node: The node to move.
        output: The name of the output holding the velocity.
        max_speed: The speed the node cannot exceed, if any.
    """
    velocity = node.data.get("outputs", {}).get(output)
    if velocity is not None:
        components = tuple(velocity)[:len(node.position)]
        speed = math.sqrt(sum(component * component for component in components))
        scale = max_speed / speed if max_speed is not None and speed > max_speed else 1.0
        node.update(tuple(
            coordinate + component * scale * delta_time
            for coordinate, component in zip(node.position, components)
        ))
    simulator.schedule_event(
        delta_time, follow_velocity, simulator, delta_time, node, output, max_speed
    )

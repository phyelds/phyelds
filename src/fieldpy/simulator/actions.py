"""
Sent of actions related to node movements and interactions in the simulator
"""


def move_with_velocity(simulator, delta_time, node, velocity):
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

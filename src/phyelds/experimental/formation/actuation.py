"""
How a robot turns the velocity it wants, in the frame of the formation, into a command
(``Actuation.kt``).
"""
from phyelds.experimental.formation.positioning import Frame
from phyelds.experimental.swarm.vector import Vector


def aligned(frame: Frame, velocity: Vector | None) -> Vector:
    """
    Actuation for a robot whose frame is aligned with that of the formation: the robots
    that fix the frame stay still, the others move by ``velocity``.

    Args:
        frame: The frame of the robot.
        velocity: The velocity it wants, ``None`` if it does not know where it is.

    Returns:
        The velocity to move by.
    """
    return Vector() if frame.is_reference or velocity is None else velocity

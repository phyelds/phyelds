"""The formation of a swarm, from positioning to actuation (``Entrypoint.kt``)."""
from collections.abc import Callable, Sequence

from phyelds.calculus import aggregate
from phyelds.experimental.formation.actuation import aligned
from phyelds.experimental.formation.control import lattice_velocity
from phyelds.experimental.formation.positioning import Frame, global_positioning, place_shape
from phyelds.experimental.formation.shapes import Shape
from phyelds.experimental.swarm.vector import Vector

Control = Callable[[Shape, Vector, Sequence[Vector]], Vector]


@aggregate
def formation(  # pylint: disable=too-many-arguments
    shape: Shape,
    *,
    reach: float,
    positioning: Callable[[], Frame] = global_positioning,
    actuation: Callable[[Frame, Vector | None], Vector] = aligned,
    control: Control | None = None,
    dimensions: int = 2,
) -> Vector:
    """
    Spread the swarm evenly over ``shape``: locate the robot, place the shape in its
    frame, compute the velocity that spreads the swarm, and turn it into a command.

    Args:
        shape: The shape to take. With a global positioning, it stays where it is; with
            the others, the swarm places it on its frame.
        reach: The radius of the Voronoi cell of ``lattice_velocity``, half the
            communication range.
        positioning: Where the robot is: ``global_positioning``,
            ``leader_positioning`` or ``anchor_positioning``.
        actuation: The command from the velocity: ``aligned``, or ``self_aligned`` for
            robots that do not know their heading.
        control: The velocity from the shape, the position and the neighbors;
            ``lattice_velocity`` if ``None``.
        dimensions: 2 to spread in the horizontal plane, 3 in space.

    Returns:
        The velocity the robot moves by.
    """
    frame = positioning()
    if frame.relative:
        shape = place_shape(frame, shape)
    velocity = None
    if frame.position is not None:
        if control is None:
            velocity = lattice_velocity(
                shape, frame.position, frame.offsets, reach=reach, dimensions=dimensions
            )
        else:
            velocity = control(shape, frame.position, frame.offsets)
    return actuation(frame, velocity)

"""
Where each robot is with respect to the shape: the positioning (``Positioning.kt``),
which builds the frame in which a robot evaluates the shape and sees its neighbors.
"""
from dataclasses import dataclass, field

from phyelds.calculus import aggregate
from phyelds.data import NeighborhoodField
from phyelds.experimental.formation.shapes import Shape
from phyelds.experimental.swarm.leader import cast_along
from phyelds.experimental.swarm.movement import neighbors_vectors
from phyelds.experimental.swarm.vector import Vector
from phyelds.libraries.device import local_id, local_position
from phyelds.libraries.leader_election import candidacy, elect_leaders
from phyelds.libraries.spreading import broadcast


@dataclass(frozen=True)
class Frame:
    """
    The view a robot has of the frame of the formation (``ReferenceFrame``).

    Attributes:
        position: The position of the robot in the frame; ``None`` until it is known.
        offsets: The vectors from the robot to its neighbors, in the frame.
        center: Where the shape is placed, in the frame.
        is_leader: Whether the robot is the leader, which places the shape.
        is_reference: Whether the robot fixes the frame, and must stay still.
        relative: Whether the swarm builds the frame, so that the shape is placed on
            ``center``; a global frame leaves the shape where it is.
    """

    position: Vector | None
    offsets: list[Vector] = field(default_factory=list)
    center: Vector = Vector()
    is_leader: bool = False
    is_reference: bool | None = None
    relative: bool = False

    def __post_init__(self):
        if self.is_reference is None:
            object.__setattr__(self, "is_reference", self.is_leader)


@aggregate
def global_positioning() -> Frame:
    """
    Position-based positioning: the frame is the global one, from the
    ``position`` sensor, shared with the neighbors to see where they are.

    Returns:
        The frame of the robot.
    """
    position = Vector(*local_position())
    return Frame(position, list(neighbors_vectors(position).exclude_self().values()))


@aggregate
def leader_positioning(
    offsets: NeighborhoodField[Vector] | None = None, bound: float = 50
) -> Frame:
    """
    Displacement-based positioning: the robots elect as leader the one with the lowest
    id within ``bound`` hops, which is the origin of the frame, and each locates itself by
    adding up the displacements along its shortest path from the leader. The leader
    fixes the frame, so it stays still.

    Args:
        offsets: The vectors from the robot to its neighbors, as it senses them in a
            frame it shares with them, such as one aligned by a compass;
            ``neighbors_vectors()`` if ``None``.
        bound: How many hops away a leader leads.

    Returns:
        The frame of the robot; without a position until it hears from the leader.
    """
    offsets = neighbors_vectors() if offsets is None else offsets
    is_leader = bool(elect_leaders(bound, strategy=candidacy(-local_id())))
    # The robot is where the neighbor on its path is, minus the vector to that neighbor.
    distance, position = cast_along(
        is_leader, Vector(), lambda there, offset: there - offset, offsets
    )
    return Frame(
        position if distance < float("inf") else None,
        list(offsets.exclude_self().values()),
        is_leader=is_leader,
        relative=True,
    )


@aggregate
def place_shape(frame: Frame, shape: Shape) -> Shape:
    """
    Place ``shape`` on a frame the swarm builds: the leader finds a point deep inside the
    shape, from the center of the frame, and spreads it; every robot moves the shape so
    that this point lies on the center. The robots that fix the frame then lie inside
    the shape, even a hollow or concave one.

    Args:
        frame: The frame of the robot.
        shape: The shape, as the program gives it.

    Returns:
        The shape, placed in the frame.
    """
    inside = shape.deepest_point_from(frame.center) if frame.is_leader else frame.center
    inside = broadcast(frame.is_leader, inside)
    return shape.translate(*(frame.center - inside))

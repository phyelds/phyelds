"""
Where each robot is with respect to the shape: the positioning (``Positioning.kt``),
which builds the frame in which a robot evaluates the shape and sees its neighbors.
"""
from dataclasses import dataclass, field

from phyelds.calculus import aggregate
from phyelds.experimental.swarm.movement import neighbors_vectors
from phyelds.experimental.swarm.vector import Vector
from phyelds.libraries.device import local_position


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

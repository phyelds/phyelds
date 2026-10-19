"""
How a robot turns the velocity it wants, in the frame of the formation, into a command
(``Actuation.kt``).
"""
from dataclasses import dataclass, replace
import math

from phyelds.calculus import aggregate, remember
from phyelds.experimental.formation.positioning import Frame
from phyelds.experimental.swarm.movement import brownian
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


@dataclass(frozen=True)
class _Alignment:
    """
    The orthogonal map, a rotation or a reflection, from the body frame to the frame of
    the formation, fit on the correlation between the changes of the estimated position
    and the robot's own motion, as in 2D Procrustes (``FrameAlignment.kt``).
    """

    xx: float = 0.0
    xy: float = 0.0
    yx: float = 0.0
    yy: float = 0.0
    energy: float = 0.0
    last_position: Vector | None = None
    last_travelled: Vector | None = None

    def _rotation_fit(self) -> float:
        return math.sqrt((self.xx + self.yy) ** 2 + (self.yx - self.xy) ** 2)

    def _reflection_fit(self) -> float:
        return math.sqrt((self.xx - self.yy) ** 2 + (self.xy + self.yx) ** 2)

    def is_confident(self, min_energy: float, min_confidence: float) -> bool:
        """Whether the robot moved enough, and in enough directions, to steer."""
        if self.energy <= min_energy:
            return False
        return abs(self._rotation_fit() - self._reflection_fit()) / self.energy > min_confidence

    def learn(
        self, position: Vector | None, travelled: Vector, forgetting: float, max_displacement: float
    ) -> "_Alignment":
        """Learn from the new estimate and the motion so far; a jump of the estimate is no move."""
        learned = self
        known = None not in (position, self.last_position, self.last_travelled)
        if known:
            estimated, moved = position - self.last_position, travelled - self.last_travelled
            if estimated.length() <= max_displacement:
                learned = _Alignment(
                    forgetting * self.xx + estimated.x * moved.x,
                    forgetting * self.xy + estimated.x * moved.y,
                    forgetting * self.yx + estimated.y * moved.x,
                    forgetting * self.yy + estimated.y * moved.y,
                    forgetting * self.energy + moved.x ** 2 + moved.y ** 2,
                )
        return replace(learned, last_position=position, last_travelled=travelled)

    def to_body(self, direction: Vector) -> Vector:
        """``direction``, from the frame of the formation to the body frame."""
        rotation, reflection = self._rotation_fit(), self._reflection_fit()
        if rotation >= reflection:
            cos, sin = (self.xx + self.yy) / rotation, (self.yx - self.xy) / rotation
            return Vector(
                cos * direction.x + sin * direction.y, -sin * direction.x + cos * direction.y
            )
        cos, sin = (self.xx - self.yy) / reflection, (self.xy + self.yx) / reflection
        return Vector(cos * direction.x + sin * direction.y, sin * direction.x - cos * direction.y)


@aggregate
def self_aligned(  # pylint: disable=too-many-arguments,too-many-locals
    frame: Frame,
    velocity: Vector | None,
    *,
    max_speed: float = 1.0,
    exploration_speed: float = 1.0,
    forgetting: float = 0.9,
    max_displacement: float = 5.0,
    min_energy: float = 5.0,
    min_confidence: float = 0.1,
    max_frame_wait: int = 50,
) -> Vector:
    """
    Actuation for a robot that does not know how its body is turned in the frame of the
    formation, as with ``anchor_positioning``: it learns the rotation, or reflection,
    from how its own commands move its estimated position, and probes the space, a step
    in a random direction and one back, until it is confident. Planar.

    Args:
        frame: The frame of the robot.
        velocity: The velocity it wants, ``None`` if it does not know where it is.
        max_speed: The speed of the command cannot exceed it.
        exploration_speed: The speed of the probing steps.
        forgetting: The fraction of the past evidence kept in each round.
        max_displacement: A change of the estimate longer than this is a jump of the
            frame, not a move.
        min_energy: How much the robot must have moved before it steers.
        min_confidence: How spread its moves must be, from 0 to 1, before it steers.
        max_frame_wait: The rounds a robot without a position waits, before probing.

    Returns:
        The command, in the body frame of the robot.
    """
    set_command, last_command = remember(Vector())
    set_travelled, travelled = remember(Vector())
    commanded = travelled.value + last_command.value
    set_travelled(commanded)
    set_alignment, alignment = remember(_Alignment())
    learned = alignment.value.learn(frame.position, commanded, forgetting, max_displacement)
    set_alignment(learned)
    set_steering, steering = remember(False)
    set_steering(steering.value or learned.is_confident(min_energy, min_confidence))
    set_probe, probe = remember((Vector(), False))
    direction, out = probe.value
    # Run and tumble: a random step out, then the same step back.
    set_probe((-direction, False) if out else (brownian(), True))
    set_waiting, waiting = remember(0)
    set_waiting(waiting.value + 1 if velocity is None else 0)
    if velocity is None:
        command = probe.value[0] * exploration_speed if waiting.value > max_frame_wait else Vector()
    elif frame.is_reference:
        command = Vector()
    elif not steering.value:
        command = probe.value[0] * exploration_speed
    else:
        command = learned.to_body(velocity)
    command = command.limit(max_speed)
    command = command if math.isfinite(command.length()) else Vector()
    set_command(command)
    return command

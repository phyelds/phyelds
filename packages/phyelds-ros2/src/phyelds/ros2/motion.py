"""How a differential-drive robot follows the ``velocity`` a program sends, as a ROS 2 twist."""
import math
from collections.abc import Sequence

# Below this speed, in m/s, a target is taken as standing still: its direction is noise.
_STILL = 1e-9


def twist(
    target: Sequence[float], *, yaw: float, max_speed: float, turn_rate: float = 1.0
) -> tuple[float, float]:
    """
    The forward and angular speed that take a robot facing ``yaw`` along ``target``.

    As on Webots and ARGoS, the robot turns towards the target velocity, in the frame of the
    world, and drives forward as much as it already faces it, never backwards.

    Args:
        target: The velocity the program sent, in m/s, in the frame of the world.
        yaw: Where the robot faces, in radians from the x axis of the world.
        max_speed: The fastest the robot moves forward, in m/s.
        turn_rate: How fast the robot turns, in rad/s for each radian it is off the target.

    Returns:
        The ``linear.x``, in m/s, and the ``angular.z``, in rad/s, of the twist.
    """
    x, y, *_ = target
    speed = min(math.hypot(x, y), max_speed)
    if speed < _STILL:
        return 0.0, 0.0
    angle = math.remainder(math.atan2(y, x) - yaw, math.tau)
    return speed * max(0.0, math.cos(angle)), turn_rate * angle


def yaw_of(x: float, y: float, z: float, w: float) -> float:
    """
    Where a robot with the orientation of a ROS quaternion faces, about the vertical axis.

    Args:
        x: The x of the quaternion.
        y: The y of the quaternion.
        z: The z of the quaternion.
        w: The w of the quaternion.

    Returns:
        The yaw, in radians from the x axis.
    """
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def body_velocity(target: Sequence[float], *, yaw: float, max_speed: float) -> tuple[float, float]:
    """
    The velocity that takes a holonomic robot facing ``yaw`` along ``target``, in its own frame.

    Args:
        target: The velocity the program sent, in m/s, in the frame of the world.
        yaw: Where the robot faces, in radians from the x axis of the world.
        max_speed: The fastest the robot moves, in m/s.

    Returns:
        The ``linear.x``, forward, and ``linear.y``, to the left, of the twist, in m/s.
    """
    x, y, *_ = target
    speed = math.hypot(x, y)
    scale = 1.0 if speed <= max_speed else max_speed / speed
    cos, sin = math.cos(yaw), math.sin(yaw)
    return scale * (cos * x + sin * y), scale * (cos * y - sin * x)


def heading_of(yaw: float) -> tuple[float, float, float]:
    """The ``heading`` sensor of a robot facing ``yaw``, in radians: a horizontal unit vector."""
    return math.cos(yaw), math.sin(yaw), 0.0


def yaw_of_heading(heading: Sequence[float]) -> float:
    """Where a robot with ``heading``, a horizontal vector, faces, in radians from the x axis."""
    return math.atan2(heading[1], heading[0])

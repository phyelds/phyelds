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

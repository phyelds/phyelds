"""
Star: the swarm spreads evenly over a star, every device taking an equal share of it.

The star is a signed distance function: negative inside, zero on its border. Each device
heads to the centroid of the part of the star closer to it than to its neighbours, and
the swarm covers the star evenly. The playground draws SHAPE under the swarm. Change
POINTS, or add devices.
"""
from phyelds.calculus import aggregate
from phyelds.experimental.formation import formation, star
from phyelds.experimental.swarm import Vector
from phyelds.libraries.device import velocity

POINTS = 5  # the tips of the star
SHAPE = star((2.5, 2.5), 2.3, POINTS)  # in the middle of the arena
REACH = 0.6  # how far a device looks for its share of the star


@aggregate
def spread_on_a_star() -> Vector:
    """Head to the centroid of the share of the star of the device: the velocity it moves by."""
    return velocity.send(formation(SHAPE, reach=REACH))

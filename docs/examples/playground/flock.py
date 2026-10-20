"""
Flock: the boids of Reynolds, every device steering as its neighbours do, and the swarm flies as one.

The three rules of the boids, each a steering weighted by how much it counts: keep apart
from the closest (separation), head as the neighbours head (alignment) and towards them
(cohesion); and turn back near the walls. The colour is the heading: a flock that agrees has one
colour. Drag a device across it, or add some more.
"""
from phyelds.calculus import aggregate, remember_and_evolve
from phyelds.experimental.swarm import Vector, alignment, avoid_obstacles, brownian, cohesion, separation
from phyelds.libraries.device import local_position, velocity

ARENA = 5.0  # the side of the arena of the playground
VISION = 2.0  # how far a boid looks at the others to align and gather
SPACE = 0.4  # how close a boid lets another come
SEPARATION, ALIGNMENT, COHESION = 0.4, 0.6, 0.02  # how much each rule turns a boid in a round
MARGIN = 0.6  # how close to a wall a boid starts turning back


def walls() -> list[Vector]:
    """The vector from the device to each wall of the arena."""
    x, y = local_position()
    return [Vector(-x, 0), Vector(ARENA - x, 0), Vector(0, -y), Vector(0, ARENA - y)]


def steer(heading: Vector) -> Vector:
    """The heading of the boid, from the one it had: the three rules, and away from the walls."""
    turn = (
        separation(heading, within=SPACE) * SEPARATION
        + alignment(heading, within=VISION) * ALIGNMENT
        + cohesion(heading, within=VISION) * COHESION
    )
    return (heading + turn + avoid_obstacles(walls(), MARGIN, norm=0.5)).normalize()


@aggregate
def flock() -> Vector:
    """Fly with the flock: the velocity the device moves by."""
    heading = remember_and_evolve(brownian(), lambda previous: steer(previous.value))
    return velocity.send(heading.value)

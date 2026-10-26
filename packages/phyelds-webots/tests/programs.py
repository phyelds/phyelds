"""Programs that the tests name in the arguments of the controller, as a world does."""
from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.device import heading, label, led, local_position, obstacle, source, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import local_time


@aggregate
def says_if_source():
    """Labels the robot with whether it is the source."""
    return label.send(f"source={source.sense()}")


@aggregate
def says_where():
    """Labels the robot with where it is and where it faces."""
    return label.send(f"position={local_position()} heading={heading.sense()}")


@aggregate
def drives_blue():
    """Lights the robot blue and drives it east, fast."""
    led.send((0, 0, 255))
    return velocity.send((1.0, 0.0))


@aggregate
def counts_neighbors():
    """Shares a value with the neighbors, to count them."""
    return neighbors(1).sum(include_self=False)


@aggregate
def says_obstacle():
    """Labels the robot with where it would move away from what it sees."""
    return label.send(f"obstacle={obstacle.sense()}")


@aggregate
def metres():
    """Labels the robot with how far it is from the source, in metres, over the radio."""
    return label.send(f"{distance_to(source.sense(), neighbors_distances()):.3f}")


@aggregate
def heads_north():
    """Drives the robot north at 5 cm/s, and labels it with the time and where it is."""
    x, y, _ = local_position()
    velocity.send((0.0, 0.05))
    return label.send(f"{local_time():.2f} {x:.3f} {y:.3f}")

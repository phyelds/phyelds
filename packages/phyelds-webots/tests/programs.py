"""Programs that the tests name in the arguments of the controller, as a world does."""
from phyelds.calculus import aggregate
from phyelds.libraries.device import heading, label, local_position, source


@aggregate
def says_if_source():
    """Labels the robot with whether it is the source."""
    return label.send(f"source={source.sense()}")


@aggregate
def says_where():
    """Labels the robot with where it is and where it faces."""
    return label.send(f"position={local_position()} heading={heading.sense()}")

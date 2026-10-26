"""Programs that the tests name in the arguments of the controller, as a world does."""
from phyelds.calculus import aggregate
from phyelds.libraries.device import label, source


@aggregate
def says_if_source():
    """Labels the robot with whether it is the source."""
    return label.send(f"source={source.sense()}")

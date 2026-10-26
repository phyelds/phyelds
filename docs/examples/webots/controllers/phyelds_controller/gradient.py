"""A metric gradient on Webots robots, without GPS: the same program as on ARGoS."""
from phyelds.calculus import aggregate
from phyelds.libraries.device import label, led, source
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


# --8<-- [start:program]
@aggregate
def main() -> float:
    """Show distance to the source, following the radio network."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(f"{distance:.2f}m")
    led.send((255, 255, 255) if source.sense() else (0, 200, 255))
    return distance
# --8<-- [end:program]

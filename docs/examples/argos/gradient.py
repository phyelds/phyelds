"""A metric gradient on ARGoS robots, without GPS."""
from phyelds.argos import label, led, source
from phyelds.calculus import aggregate
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


@aggregate
def main() -> float:
    """Show distance to the source, following the radio network."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(f"{distance:.2f}m")
    led.send((255, 255, 255) if source.sense() else (0, 200, 255))
    return distance

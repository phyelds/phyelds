"""A metric gradient on ARGoS robots, without GPS."""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


@aggregate
def main() -> float:
    """Show distance to the source, following the radio network."""
    distance = float(distance_to(sense("source"), neighbors_distances()))
    store("label", f"{distance:.2f}m")
    store("led", (255, 255, 255) if sense("source") else (0, 200, 255))
    return distance

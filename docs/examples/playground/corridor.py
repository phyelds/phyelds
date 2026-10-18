"""
Corridor: the devices within WIDTH of the shortest path between a source and a target.

A gradient, a collection along it and a second gradient, as the tutorial builds it: try changing WIDTH.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.collect import collect_or
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

WIDTH = 0.8  # how far from the path a device still belongs to the channel


@aggregate
def corridor() -> float:
    """1.0 on the devices within WIDTH of the shortest path from the source to the target, 0.0 elsewhere."""
    distances = neighbors_distances()
    to_target = distance_to(sense("target"), distances)
    on_path = collect_or(to_target, sense("source"))
    return 1.0 if distance_to(on_path, distances) < WIDTH else 0.0

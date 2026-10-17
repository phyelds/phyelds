"""
Channel: the devices between a source and a target form a band along the shortest path.

It combines two gradients and a collection: try changing WIDTH.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.collect import collect_or
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

WIDTH = 0.8  # how far from the path a device still belongs to the channel


@aggregate
def channel() -> bool:
    """Whether the device is close to the path from the source to the target."""
    distances = neighbors_distances()
    to_target = distance_to(sense("target"), distances)
    on_path = collect_or(to_target, sense("source"))
    return distance_to(on_path, distances) < WIDTH

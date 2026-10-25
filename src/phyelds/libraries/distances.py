"""
This module contains functions to calculate distances between nodes in the neighborhood.
These functions may be used by other library to compute system-wise properties
"""

from collections.abc import Sequence
import math

from phyelds.calculus import neighbors, aggregate
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id, local_position, sense


@aggregate
def neighbors_distances(
    position: Sequence[float] | None = None,
) -> NeighborhoodField[float]:
    """
    Read measured neighbor distances, or compute them from shared positions.

    Args:
        position: Optional coordinate sequence for the current node. When
            omitted, the ``neighbors_distances`` sensor (an ID-to-distance map)
            is used if present, otherwise ``local_position()`` is used.
            Supports any dimension (2D, 3D, N-D). Measured distances use the
            host's units and only include neighbors aligned at this call.

    Returns:
        A ``NeighborhoodField[float]`` with the distance to each neighbor
            (0.0 for the local node).
    """
    measured = sense("neighbors_distances")
    if position is None and measured is not None:
        peers = neighbors(None).exclude_self()
        data = {node_id: float(measured[node_id]) for node_id in peers if node_id in measured}
        data[local_id()] = 0.0
        return NeighborhoodField(data, local_id(), default=float("inf"))
    my_position = tuple(local_position() if position is None else position)
    positions: NeighborhoodField[tuple[float, ...]] = neighbors(my_position)
    return positions.map(lambda other: math.dist(my_position, other))


@aggregate
def hops_distance() -> NeighborhoodField[int]:
    """
    Return the distance to each neighbor in hops.

    Returns:
        A field that is ``1`` for every neighbor and ``0`` for the current device.
    """
    distances: NeighborhoodField[int] = neighbors(1)
    distances.data[local_id()] = 0
    return distances

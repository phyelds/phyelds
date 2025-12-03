"""
Collect library
functions that are used to collect information from the network to source nodes.
"""

from typing import Callable, Optional, TypeVar, Union, Tuple
from phyelds.calculus import neighbors, aggregate, remember
from phyelds.data import NeighborhoodField, StateT
from phyelds.libraries.device import local_id

T = TypeVar("T")


@aggregate
def find_parent(potential: StateT[float]) -> Optional[int]:
    """
    Find the parent of a path giving a potential neighborhood.

    :param potential: The potential value (distance/gradient) at the current node.
    :return: The node ID of the parent (neighbor with min potential), or None if local is min.
    """
    neighbors_potential: NeighborhoodField[float] = neighbors(potential)

    # We are finding the item (id, value) with the minimum value
    min_value: Tuple[int, float] = min(neighbors_potential.data.items(), key=lambda x: x[1])

    if min_value[1] >= potential:
        return None
    return min_value[0]


@aggregate
def collect_with(
    potential: StateT[float],
    local: T,
    accumulation: Callable[[T, T], T]
) -> StateT[T]:
    """
    Generic collection function that accumulates data from children to parents
    based on a potential neighborhood.

    :param potential: The potential neighborhood used to determine parent-child relationships.
    :param local: The local value to start with (and add to).
    :param accumulation: A function to combine two values (e.g., sum, max, union).
    :return: The accumulated state.
    """
    # set_collections is the update function, collections is the State object
    set_collections, collections = remember(local)

    n_collections: NeighborhoodField[T] = neighbors(collections)
    parents: NeighborhoodField[Optional[int]] = neighbors(find_parent(potential))

    # zip iterates over the aligned values of the neighborhoods
    zip_operation = zip(parents, n_collections)

    operations: T = local

    for parent, value in zip_operation:
        # parent is Optional[int], value is T
        if local_id() == parent:
            operations = accumulation(operations, value)

    set_collections(operations)
    return collections


@aggregate
def count_nodes(potential: StateT[float]) -> StateT[int]:
    """
    Count the number of nodes in the sub-tree defined by the potential neighborhood.

    :param potential: The potential field.
    :return: The count of nodes.
    """
    return collect_with(potential, 1, lambda x, y: x + y)


@aggregate
def sum_values(potential: StateT[float], local: Union[int, float]) -> StateT[Union[int, float]]:
    """
    Sum numeric values up the potential gradient.

    :param potential: The potential field.
    :param local: The local numeric value.
    :return: The sum of values.
    """
    return collect_with(potential, local, lambda x, y: x + y)


@aggregate
def collect_or(potential: float, local: bool) -> StateT[bool]:
    """
    Perform a logical OR collection up the potential gradient.
    Useful for determining if *any* node in a subtree satisfies a condition.

    :param potential: The potential field.
    :param local: The local boolean condition.
    :return: True if any node in the subtree is True.
    """
    return collect_with(potential, local, lambda x, y: x or y)

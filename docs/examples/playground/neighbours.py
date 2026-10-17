"""
Neighbours: every device counts the devices within its communication range.

Add devices, or drag them apart: the count follows, round after round.
"""
from phyelds.calculus import aggregate, neighbors


@aggregate
def neighbour_count() -> int:
    """How many devices this device hears, itself excluded."""
    return len(neighbors(1).exclude_self())

"""
Which devices run together: the rule that picks the next wavefront from the pending rounds.
"""
from collections.abc import Hashable, Iterable, Mapping

WorldNeighbors = Mapping[Hashable, Iterable[Hashable]]


def select_wavefront(
    next_times: Mapping[Hashable, float],
    neighbors: WorldNeighbors,
    *,
    lookahead: float,
    delay: float,
    until: float | None = None,
) -> list[Hashable]:
    """
    Pick the devices that run their next round together, in the next wavefront.

    A device runs if its next round comes within ``lookahead`` of the earliest pending round
    (and not after ``until``), and no neighbor can still send it a message that arrives by
    then: a neighbor ``u`` blocks a device ``v`` when ``t_u + delay <= t_v``, as a message
    arriving at the time of a round is read in it. With ``delay`` zero, of two neighbors due
    at the same time the one that comes first in ``next_times`` runs first.

    Args:
        next_times: The time of the next round of each device, in the order of the devices.
        neighbors: The ids of the neighbors of each device; ids missing from ``next_times``
            are ignored.
        lookahead: How far past the earliest pending round a wavefront reaches.
        delay: How long a message takes, at the least, to reach a neighbor.
        until: The time after which no round runs; none by default.

    Returns:
        The devices of the wavefront, in the order of ``next_times``; empty if no round is
            due by ``until``.
    """
    if not next_times:
        return []
    earliest = min(next_times.values())
    if until is not None and earliest > until:
        return []
    cap = earliest + lookahead
    if until is not None:
        cap = min(cap, until)

    rank = {dev: idx for idx, dev in enumerate(next_times)}
    selected: list[Hashable] = []
    for dev, t_dev in next_times.items():
        if t_dev > cap:
            continue
        blocked = False
        for peer in neighbors.get(dev, ()):
            if peer == dev or peer not in rank:
                continue
            arrival = next_times[peer] + delay
            if arrival < t_dev or (
                arrival == t_dev and (delay > 0.0 or rank[peer] < rank[dev])
            ):
                blocked = True
                break
        if not blocked:
            selected.append(dev)
    return selected

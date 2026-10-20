"""
Opinions: every device averages its vote with what its neighbours think, and the votes blur into a map.

A device votes 1 when `vote` is on, 0 otherwise, and keeps averaging its vote with the
estimates of its neighbours: an estimate is high where many devices around vote yes.
Switch `vote` on for a group of devices, then for a lone one far away.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.gossip import gossip_mean


@aggregate
def opinion() -> float:
    """How much the devices around this one vote yes."""
    return gossip_mean(1.0 if sense("vote") else 0.0)

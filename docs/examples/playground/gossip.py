"""
Gossip: every device learns the highest value of the network, and forgets one that is gone.

A device worth 100 when `high` is on, its id otherwise. gossip_max keeps a maximum
forever; stabilizing_gossip recomputes it every round from the values within DIAMETER
hops. Switch `high` off and watch both: `remembered` stays at 100, the result does not.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max, stabilizing_gossip

DIAMETER = 10  # how many hops a value travels: at least the diameter of the network


@aggregate
def highest() -> float:
    """The highest value among the devices within DIAMETER hops."""
    value = 100.0 if sense("high") else float(local_id())
    remembered = gossip_max(value)  # noqa: F841 (not returned, but there to watch)
    return stabilizing_gossip(value, DIAMETER, max)

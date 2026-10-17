"""
Bubbles: an aggregate process spawns on an alarm, expands up to a radius, and shuts down.

Switch `alarm` on for a device to start a bubble, then `clear` on the same device to end it.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.processes import in_bubble, process, terminate_if
from phyelds.libraries.spreading import distance_to

MAX_HOPS = 2.0  # spatial radius of the process bubble


@process
def alert_bubble(origin: int) -> float:
    """Expand up to MAX_HOPS from `origin` and shut down when the origin clears."""
    is_origin = local_id() == origin
    hops = float(distance_to(is_origin))
    terminate_if(is_origin and sense("clear"))
    in_bubble(hops <= MAX_HOPS)
    return MAX_HOPS - hops + 1.0


@aggregate
def monitor_alerts() -> float:
    """Spawn an alert bubble when `alarm` is sensed; return 0.0 outside the bubble."""
    keys = {local_id()} if sense("alarm") else set()
    active = alert_bubble.spawn(keys)
    return max(active.values(), default=0.0)

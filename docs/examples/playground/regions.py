"""
Regions: the devices on the boundary of a zone, found from their neighbours alone.

Switch `zone` on for a block of devices: a device is in the interior when it and all its
neighbours are in the zone, and on the boundary when it is in the zone or next to it, but
not in its interior, as `boundary(zone)` says in one call. Watch `inside` and `near`: a
thin zone has no interior.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.logic import closure, interior


@aggregate
def border() -> bool:
    """Whether the device is on the boundary of the zone."""
    zone = bool(sense("zone"))
    inside = interior(zone)
    near = closure(zone)
    return near and not inside

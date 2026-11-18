"""Turtles that measure how far the source turtle is, over the network, and gather around it."""
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import sink_at, stand_still
from phyelds.libraries.device import label, source, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

NEAR = 1.5
"""How close to the source a turtle stops, in metres."""

SPEED = 1.0
"""How fast a turtle heads to the source, in m/s."""


# --8<-- [start:program]
@aggregate
def main() -> float:
    """Show the distance to the source, and head to it along the network until near."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(f"{distance:.1f}m")
    # Every turtle computes the way to the source, near or not, so that all of them align.
    to_source = sink_at(source.sense())
    velocity.send(to_source * SPEED if distance > NEAR else stand_still())
    return distance
# --8<-- [end:program]

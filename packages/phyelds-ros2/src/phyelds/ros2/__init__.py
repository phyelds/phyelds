"""
Run phyelds programs on ROS 2 robots, one node per robot.

Each node is a device: its messages travel as bytes on a topic that all the nodes share, and
a neighbourhood strategy decides which senders are its neighbours.
"""
from phyelds.ros2.aggregate_node import AggregateNode
from phyelds.ros2.host import AggregateRosNode, main
from phyelds.ros2.neighbourhood import (
    Neighbour,
    Neighbourhood,
    Reachable,
    Transforms,
    WithinRange,
)

__all__ = [
    "AggregateNode", "AggregateRosNode", "Neighbour", "Neighbourhood", "Reachable", "Transforms",
    "WithinRange", "main",
]

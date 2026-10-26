"""
Run phyelds programs on the robots of a [Webots](https://cyberbotics.com) simulation.

Each robot runs its own controller, so each robot is a device: its messages travel as bytes
from its ``Emitter`` to the ``Receiver`` of the robots in range.
"""
from phyelds.webots.aggregate_controller import AggregateController
from phyelds.webots.body import Body

__all__ = ["AggregateController", "Body"]

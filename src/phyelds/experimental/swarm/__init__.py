"""
Swarm behaviours: blocks that compute where a robot moves, to be summed and weighted.

The blocks of *MacroSwarm: A Field-based Compositional Framework for Swarm Programming*
(Aguzzi, Casadei, Viroli, LMCS 2025, https://doi.org/10.46298/lmcs-21(3:13)2025), after
their ScaFi implementation (https://github.com/scafi/macro-swarm). Each block is an
aggregate function that returns a ``Vector``: a velocity, or a heading to scale.
"""
from phyelds.experimental.swarm.vector import Vector

__all__ = ["Vector"]

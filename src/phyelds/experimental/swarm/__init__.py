"""
Swarm behaviours: blocks that compute where a robot moves, to be summed and weighted.

The blocks of *MacroSwarm: A Field-based Compositional Framework for Swarm Programming*
(Aguzzi, Casadei, Viroli, LMCS 21(3), 2025, https://arxiv.org/abs/2401.10969), after
their ScaFi implementation (https://github.com/scafi/macro-swarm). Each block is an
aggregate function that returns a ``Vector``: a velocity, or a heading to scale.
"""
from phyelds.experimental.swarm.flocking import (
    alignment,
    cohesion,
    cucker_smale,
    reynolds,
    separation,
    vicsek,
)
from phyelds.experimental.swarm.leader import (
    Team,
    align_with_leader,
    is_team_formed,
    sink_at,
    spin_around,
    team_formation,
)
from phyelds.experimental.swarm.movement import (
    avoid_obstacles,
    brownian,
    explore,
    go_to,
    is_close,
    maintain_trajectory,
    maintain_until,
    neighbors_vectors,
    stand_still,
)
from phyelds.experimental.swarm.vector import Vector

__all__ = [
    "Team",
    "Vector",
    "align_with_leader",
    "alignment",
    "avoid_obstacles",
    "brownian",
    "cohesion",
    "cucker_smale",
    "explore",
    "go_to",
    "is_close",
    "is_team_formed",
    "maintain_trajectory",
    "maintain_until",
    "neighbors_vectors",
    "reynolds",
    "separation",
    "sink_at",
    "spin_around",
    "stand_still",
    "team_formation",
    "vicsek",
]

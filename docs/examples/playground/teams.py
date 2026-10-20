"""
Teams: the swarm splits into teams around elected leaders, and every team wanders on its own.

Leaders are elected about EXTRA / 2 apart; the devices gather around the nearest one,
INTRA apart, and once its team is formed, every leader wanders around the arena with its
team, apart from the others. The colour is the leader of the team.
"""
from phyelds.calculus import aggregate
from phyelds.experimental.swarm import (
    Vector, align_with_leader, explore, is_team_formed, separation, sink_at, team_formation,
)
from phyelds.libraries.device import local_id, velocity

INTRA = 0.4  # how far the members of a team keep from each other
EXTRA = 6.0  # the leaders are elected about half this far apart
LOWEST, HIGHEST = (0.5, 0.5), (4.5, 4.5)  # where the leaders wander, inside the arena


def wander(leader: int) -> Vector:
    """Move as the leader of the team, which wanders, close to it and apart from the others."""
    is_leader = local_id() == leader
    heading = align_with_leader(is_leader, explore(LOWEST, HIGHEST))
    keep = sink_at(is_leader) * 0.5 + separation(Vector(), within=INTRA) * 2
    return heading if is_leader else heading + keep


@aggregate
def teams() -> int:
    """Gather, then wander, in the team of the device; the leader of the team."""
    team = team_formation(INTRA, EXTRA, condition=lambda leader: is_team_formed(leader, INTRA * 2))
    velocity.send(team.inside(wander))
    return team.leader

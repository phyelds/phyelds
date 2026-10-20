"""
Teams: the swarm splits into teams around elected leaders, and every team roams its own area.

Leaders are elected about EXTRA / 2 apart while the swarm stands still; after SETTLE
rounds they are kept, and the devices gather around the nearest one, INTRA apart. Once
gathered, the team is formed: its leader roams around where the team formed, and the
team moves as it does, apart from the others. The colour is the heading, the same in a
team; watch `team` for its leader.
"""
from phyelds.calculus import aggregate, remember
from phyelds.experimental.swarm import (
    Vector, align_with_leader, explore, is_team_formed, separation, sink_at, team_formation,
)
from phyelds.libraries.device import local_id, local_position, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import elect_leaders
from phyelds.libraries.time import local_time

INTRA = 0.4  # how far the members of a team keep from each other
EXTRA = 3.0  # the leaders are elected about half this far apart
SETTLE = 10  # rounds the election takes to settle, while the swarm stands still
ROAM = 1.0  # how far from where its team formed a leader roams
LOWEST, HIGHEST = 0.3, 4.7  # the arena of the playground, a little inside its walls


def roam(leader: int) -> Vector:
    """Move as the leader of the team, which roams around where the team formed, close to it."""
    is_leader = local_id() == leader
    _, home = remember(local_position())  # where the device was when its team formed
    lowest = tuple(max(LOWEST, value - ROAM) for value in home.value)
    highest = tuple(min(HIGHEST, value + ROAM) for value in home.value)
    heading = align_with_leader(is_leader, explore(lowest, highest))
    keep = sink_at(is_leader) * 0.5 + separation(Vector(), within=INTRA) * 2
    return heading if is_leader else heading + keep


@aggregate
def teams() -> Vector:
    """Gather, then roam, in the team of the device: the velocity the device moves by."""
    elected = elect_leaders(EXTRA, neighbors_distances())
    # The leaders elected while the swarm stood still: moving would change who is elected.
    set_leader, is_leader = remember(False)
    settling = local_time() <= SETTLE
    if settling:
        set_leader(elected)

    def formed(leader: bool) -> bool:
        # Checked on every device, settling or not, so that the checks stay aligned.
        return is_team_formed(leader, INTRA * 2) and not settling

    team = team_formation(INTRA, EXTRA, leader=is_leader.value, condition=formed)
    moving = team.inside(roam)
    return velocity.send(Vector() if settling else moving)

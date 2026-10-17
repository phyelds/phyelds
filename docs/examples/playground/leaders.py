"""
Leaders: the network elects sparse leaders and partitions itself into Voronoi clusters.

Change GRAIN to control the radius of each cluster and how many leaders emerge.
"""
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import candidacy, elect_leaders
from phyelds.libraries.spreading import broadcast

GRAIN = 2.0  # minimum distance between elected leaders


@aggregate
def cluster_id() -> float:
    """Elect sparse leaders and broadcast each leader's ID across its Voronoi region."""
    distances = neighbors_distances()
    is_leader = elect_leaders(GRAIN, distances, strategy=candidacy())
    return float(broadcast(is_leader, local_id(), distances))

import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import (
    Candidacy,
    candidacy,
    elect_leader,
    elect_leaders,
    uuid_competition,
)
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator

def prepare_leader_election(area:float = 6, size = 5):
    """
    Prepare the simulator for the leader election test.
    """
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        return elect_leaders(area, neighbors_distances())
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    return simulator

@pytest.mark.parametrize("_", range(100))
def test_leader_election_should_elect_one_leader_with_large_grain(_):
    """
    Test the leader election algorithm with a large grain.
    """
    simulator = prepare_leader_election(area=10)
    # Assert, just one leader
    leaders = [node for node in simulator.environment.nodes.values() if node.data["result"] == 1]
    assert len(leaders) == 1

@pytest.mark.parametrize("_", range(100))
def test_leader_election_should_split_the_space_coherently(_):
    """
    Test the leader election algorithm with a small grain.
    """
    simulator = prepare_leader_election(size=5, area=2.5)
    leaders = [node for node in simulator.environment.nodes.values() if node.data["result"] == 1]
    assert 2 <= len(leaders) <= 4


@pytest.mark.parametrize("invalid_area", [float("inf"), float("-inf"), float("nan"), 0.0, -5.0])
def test_leader_election_rejects_non_positive_or_non_finite_area(invalid_area):
    with pytest.raises(ValueError):
        elect_leader(invalid_area)
    with pytest.raises(ValueError):
        elect_leaders(invalid_area)


def test_candidacy_elects_leader_and_self_stabilizes_quickly_on_leader_removal():
    size = 5
    simulator = setup_up_simulator(size)

    @aggregate
    def program():
        leader = elect_leader(area=50.0, strategy=candidacy())
        is_me = elect_leaders(area=50.0, strategy=candidacy())
        return leader, is_me

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(6)
    for node_id, node in simulator.environment.nodes.items():
        assert node.data["result"] == (4, node_id == 4)

    # Remove leader 4: even though area=50.0, loop-free candidacy heals in <= 6 rounds
    simulator.environment.remove_node(4)
    simulator.continue_run(6)
    for node_id, node in simulator.environment.nodes.items():
        assert node.data["result"] == (3, node_id == 3)


def test_candidacy_bounded_election_splits_space_and_respects_strength():
    size = 6
    simulator = setup_up_simulator(size)

    @aggregate
    def program():
        # Prefer smaller IDs by using -local_id() as strength, with bound=2.0 hops
        return elect_leader(area=2.0, strategy=candidacy(strength=lambda: -local_id()))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(8)
    results = [simulator.environment.nodes[i].data["result"] for i in range(size)]
    # Node 0 covers 0, 1, 2 (distance <= 2); Node 3 covers 3, 4, 5 (distance <= 2)
    assert results == [0, 0, 0, 3, 3, 3]
    c1 = Candidacy(candidate=0, distance=1.0, strength=10)
    c2 = Candidacy(candidate=1, distance=0.0, strength=5)
    assert c2 < c1


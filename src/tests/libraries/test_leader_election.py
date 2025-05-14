from phyelds.calculus import aggregate
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.leader_election import elect_leaders
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
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(10)
    return simulator

def test_leader_election_should_elect_one_leader_with_large_grain():
    """
    Test the leader election algorithm with a large grain.
    """
    simulator = prepare_leader_election()
    # Assert, just one leader
    leaders = [node for node in simulator.environment.nodes.values() if node.data["result"] == 1]
    assert len(leaders) == 1

def test_leader_election_should_split_the_space_coherently():
    """
    Test the leader election algorithm with a small grain.
    """
    simulator = prepare_leader_election(size=5, area=2.5)
    # Assert, just one leader
    leaders = [node for node in simulator.environment.nodes.values() if node.data["result"] == 1]
    assert len(leaders) == 2
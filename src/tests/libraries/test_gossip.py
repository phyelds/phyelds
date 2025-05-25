from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to, cast_from, broadcast
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator

ITERATIONS = 10

def test_distance_to_should_compute_the_multi_hop_distance_from_source():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        return gossip_max(local_id())
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # for all node result should be the max id, which is size - 1
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1)

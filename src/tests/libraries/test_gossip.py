from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, local_id
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.gossip import gossip_max, gossip_min, gossip, stabilizing_gossip
from phyelds.libraries.spreading import distance_to, cast_from, broadcast
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator

ITERATIONS = 10

def test_gossip_max_min_should_gossip_the_correct_values():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        max = gossip_max(local_id())
        min = gossip_min(local_id())
        all_ids = gossip({local_id()}, set.union)
        return (max, min, all_ids)
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # for all node result should be (size - 1, 0)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1, 0, set(range(size)))

def test_stabilizing_gossip_should_adapt_to_network_changes():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        return stabilizing_gossip(local_id(), 10, max)
    # Act
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # for all node result should be (size - 1, 0)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1)

    # remove the last node
    simulator.environment.remove_node(size - 1)
    simulator.run(ITERATIONS + ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 2)

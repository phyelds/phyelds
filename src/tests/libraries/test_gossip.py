from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import (
    any_node,
    gossip,
    gossip_max,
    gossip_mean,
    gossip_min,
    monotonic_gossip,
    path_coherent_gossip,
    stabilizing_gossip,
    time_replicated_gossip,
)
import pytest
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
    schedule_program_for_all(simulator, 0.0,1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # for all node result should be (size - 1, 0)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1, 0, set(range(size)))

def test_normal_gossip_does_not_heal():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        return gossip_max(local_id())
    # Act
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    # Assert
    # for all node result should be (size - 1, 0)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1)

    # remove the last node
    simulator.environment.remove_node(size - 1)
    simulator.run(ITERATIONS + ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (size - 1)

def test_stabilizing_gossip_should_adapt_to_network_changes():
    size = 5
    # 0 - 1 - 2 - 3 - 4
    simulator = setup_up_simulator(size)
    @aggregate
    def program():
        return stabilizing_gossip(local_id(), 10, max)
    # Act
    schedule_program_for_all(simulator, 0.0, 1.0, program)
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


def test_gossip_max_and_min_support_key_parameter():
    simulator = setup_up_simulator(4)

    @aggregate
    def program():
        item = f"node_{local_id()}", (local_id() - 2) ** 2
        best = gossip_max(item, key=lambda pair: pair[1], strategy=monotonic_gossip())
        worst = gossip_min(item, key=lambda pair: pair[1])
        return best[0], worst[0]

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == ("node_0", "node_2")


def test_path_coherent_gossip_and_any_node_self_stabilize_on_value_and_topology_change():
    size = 5
    simulator = setup_up_simulator(size)
    simulator.environment.nodes[4].data["alarm"] = True
    for i in range(size - 1):
        simulator.environment.nodes[i].data["alarm"] = False

    @aggregate
    def program():
        active_alarm = any_node(sense("alarm"), strategy=path_coherent_gossip(max_diameter=10))
        ever_alarm = any_node(sense("alarm"))
        highest = gossip_max(local_id(), strategy=path_coherent_gossip(max_diameter=10))
        return active_alarm, ever_alarm, highest

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (True, True, 4)

    # Turn off alarm on node 4 (value change without removing node)
    simulator.environment.nodes[4].data["alarm"] = False
    simulator.continue_run(ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (False, True, 4)

    # Remove node 4: highest heals to 3
    simulator.environment.remove_node(4)
    simulator.continue_run(ITERATIONS)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == (False, True, 3)


def test_time_replicated_gossip_heals_combining_reducers_like_set_union():
    simulator = setup_up_simulator(4)

    @aggregate
    def program():
        return gossip(
            frozenset({local_id()}),
            frozenset.union,
            strategy=time_replicated_gossip(period=4.0, max_replicas=2),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == frozenset({0, 1, 2, 3})

    simulator.environment.remove_node(3)
    simulator.continue_run(12)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == frozenset({0, 1, 2})


def test_gossip_mean_converges_to_harmonic_equilibrium_and_self_stabilizes():
    simulator = setup_up_simulator(3)

    @aggregate
    def program():
        return gossip_mean(float(local_id() * 30))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(25)
    # On line 0 - 1 - 2 with inputs 0, 30, 60:
    # equilibrium is x1 = (x0 + 30 + x2)/3 = 30, x0 = (0 + 30)/2 = 15, x2 = (30 + 60)/2 = 45
    assert simulator.environment.nodes[0].data["result"] == pytest.approx(15.0, abs=1e-2)
    assert simulator.environment.nodes[1].data["result"] == pytest.approx(30.0, abs=1e-2)
    assert simulator.environment.nodes[2].data["result"] == pytest.approx(45.0, abs=1e-2)



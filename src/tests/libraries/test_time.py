import pytest
from phyelds.calculus import aggregate, remember
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.time import (
    counter,
    decay,
    delta_time,
    local_time,
    shared_clock,
    time_replicated,
    timer,
)
from phyelds.simulator import Simulator, Node
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator

def test_counter():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)
    @aggregate
    def program():
        return counter()
    schedule_program_for_all(simulator, 1.0, 1.0, program)
    simulator.run(10)
    assert node.data["result"] == 10

def test_local_time_should_be_aligned_with_simulator_time():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)
    @aggregate
    def program():
        return local_time()
    schedule_program_for_all(simulator, 0.1, 1.0, program)
    simulator.run(1)
    assert node.data["result"] == 0.1

def test_decay_should_decay_value_over_time():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)
    @aggregate
    def program():
        decay_result = decay(10, 1)
        return decay_result
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(4)
    assert node.data["result"] == 5
    simulator.continue_run(5)
    assert node.data["result"] == 0
    simulator.continue_run(5)
    assert node.data["result"] == 0


def test_decay_should_restart():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)
    @aggregate
    def program():
        set_should_decay, should_decay = remember(True)
        decay_result = 0
        if should_decay:
            decay_result = decay(10, 1)
            set_should_decay(decay_result > 0)
        else:
            set_should_decay(True)
        return decay_result
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    assert node.data["result"] == 0
    simulator.continue_run(1)
    assert node.data["result"] == 9


def test_delta_time_returns_zero_on_first_round_and_interval_after():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)

    @aggregate
    def program():
        return delta_time()

    schedule_program_for_all(simulator, 0.0, 2.5, program)
    simulator.run(0.0)
    assert node.data["result"] == 0.0
    simulator.continue_run(2.5)
    assert node.data["result"] == 2.5


def test_shared_clock_follows_fastest_node_and_continues_after_removal():
    simulator = setup_up_simulator(3)
    for node_id, node in simulator.environment.nodes.items():
        node.data["offset"] = 10.0 if node_id == 0 else 0.0

    @aggregate
    def program():
        return shared_clock(local_time() + sense("offset"))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(5)
    # Node 0 is at local_time 5 + offset 10 = 15.0; nodes 1 and 2 adopt 15.0
    for node in simulator.environment.nodes.values():
        assert node.data["result"] >= 14.0

    # Remove the fast node 0: remaining nodes keep advancing from the shared clock
    before_removal = simulator.environment.nodes[1].data["result"]
    simulator.environment.remove_node(0)
    simulator.continue_run(3)
    assert simulator.environment.nodes[1].data["result"] > before_removal


def test_timer_counts_down_and_restarts_when_periodic():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)

    @aggregate
    def program():
        return timer(3.0, periodic=True)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(0.0)
    assert node.data["result"] == 3.0
    simulator.continue_run(2.0)
    assert node.data["result"] == 1.0
    simulator.continue_run(1.0)
    assert node.data["result"] <= 0.0
    simulator.continue_run(1.0)
    assert node.data["result"] == 2.0


def test_time_replicated_heals_non_stabilizing_gossip_after_node_removal():
    simulator = setup_up_simulator(4)

    @aggregate
    def max_id_process():
        return gossip_max(local_id())

    @aggregate
    def program():
        return time_replicated(max_id_process, period=4.0, max_replicas=2)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == 3

    # Remove node 3: plain gossip_max would stay at 3 forever,
    # but time_replicated spawns fresh replicas and converges to 2.
    simulator.environment.remove_node(3)
    simulator.continue_run(12)
    for node in simulator.environment.nodes.values():
        assert node.data["result"] == 2


def test_time_replicated_validates_arguments():
    with pytest.raises(ValueError):
        time_replicated(lambda: 1, period=0.0)
    with pytest.raises(ValueError):
        time_replicated(lambda: 1, period=5.0, max_replicas=0)


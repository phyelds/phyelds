from phyelds.calculus import aggregate, remember
from phyelds.libraries.time import counter, decay
from phyelds.simulator import Simulator, Node
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.libraries.time import local_time

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

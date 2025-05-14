from phyelds.calculus import aggregate
from phyelds.libraries.time import counter
from phyelds.simulator import Simulator, Node
from phyelds.simulator.runner import schedule_program_for_all


def test_counter():
    simulator = Simulator()
    node = Node(node_id=1, position=(0, 0))
    simulator.environment.add_node(node)
    @aggregate
    def program():
        return counter()
    schedule_program_for_all(simulator, 1.0, program)
    simulator.run(10)
    assert node.data["result"] == 10
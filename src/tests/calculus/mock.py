from phyelds.internal import MutableEngine

from phyelds import engine
from phyelds.abstractions import NodeContext


class MockNodeContext(NodeContext):
    """
    Mock NodeContext for testing purposes.
    """

    def __init__(self, node_id: int):
        super().__init__(node_id=node_id, sensors={})

    def __repr__(self):
        return f"MockNodeContext(node_id={self.node_id})"

    def __str__(self):
        return f"MockNodeContext with ID: {self.node_id}"

class MockNode:
    def __init__(self, position: tuple, node_id: int):
        self.position = position
        self.node_id = node_id
        self.context = {
            'messages': {},
            "state": {},
            "node_context": MockNodeContext(node_id),
        }
        self.root = None

    def get_position(self):
        return self.position

    def get_node_id(self):
        return self.node_id

class MockSimulator:
    def __init__(self, how_many: int = 1):
        self.nodes = [MockNode((i, i), node_id=i) for i in range(how_many)]

    def cycle(self, program):
        for node in self.nodes:
            all_messages = {
                neighbor.node_id: neighbor.context["messages"]
                for neighbor in self.nodes if neighbor.node_id != node.node_id
            }
            engine.set(
                MutableEngine().setup(node.context["node_context"], all_messages, node.context["state"])
            )
            node.root = program()
            node.context["messages"] = engine.get().cooldown()
            node.context["state"] = engine.get().state_trace()
    def cycle_for(self, program, how_many: int):
        for _ in range(how_many):
            self.cycle(program)
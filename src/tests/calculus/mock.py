from fieldpy import engine


class MockNode:
    def __init__(self, position: tuple, node_id: int):
        self.position = position
        self.node_id = node_id
        self.context = {
            'messages': {},
            "state": {},
            "node_id": node_id,
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
            engine.setup(node.node_id, all_messages, node.context["state"])
            node.root = program(node)
            node.context["messages"] = engine.cooldown()
            node.context["state"] = engine.state_trace()
    def cycle_for(self, program, how_many: int):
        for _ in range(how_many):
            self.cycle(program)
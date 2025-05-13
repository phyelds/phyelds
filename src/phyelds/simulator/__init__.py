"""
A simple simulator for aggregate computing systems in phyelds.
This simulator allows you to create nodes, set their positions and data,
and define their neighborhoods.
It also provides a way to schedule events and run the simulation.
"""

from typing import Dict, Callable, Any, Optional, Tuple, List
import heapq
import uuid


class Node:
    """
    A class to represent a node in the simulation.
    """

    def __init__(
        self, position: Tuple[float, ...], data: Any = None, node_id: any = None
    ):
        if node_id == 0:
            self.id = 0
        else:
            self.id = node_id or str(uuid.uuid4())
        self.position = position
        if data is None:
            data = {}
        self.data = data
        self.environment = None

    def update(
        self, new_position: Optional[Tuple[float, ...]] = None, new_data: Any = None
    ):
        """Update node position and/or data"""
        if new_position is not None:
            self.position = new_position
        if new_data is not None:
            self.data = new_data
        if self.environment:
            self.environment.node_updated(self)

    def get_neighbors(self):
        """Get neighboring nodes from the environment"""
        if self.environment:
            return self.environment.get_neighbors(self)
        return []


class Environment:
    """
    A class to represent the environment in which nodes exist.
    It manages the nodes and their neighborhoods.
    It also provides a way to set the neighborhood function.
    """

    def __init__(
        self, neighborhood_function: Callable[[Node, List[Node]], List[Node]] = None
    ):
        self.nodes: Dict[any, Node] = {}
        self.neighborhood_function = neighborhood_function or self.no_neighbors

    def add_data_for_all_nodes(self, data: Dict[str, Any]):
        """Add data to all nodes in the environment"""
        for node in self.nodes.values():
            node.data.update(data)

    def node_list(self) -> List[Node]:
        """Return a list of all nodes in the environment"""
        return list(self.nodes.values())

    def add_node(self, node: Node):
        """Add a node to the environment"""
        self.nodes[node.id] = node
        node.environment = self

    def remove_node(self, node_id: str):
        """Remove a node from the environment"""
        if node_id in self.nodes:
            self.nodes[node_id].environment = None
            del self.nodes[node_id]

    def node_updated(self, node: Node):
        """Called when a node is updated"""

    def set_neighborhood_function(self, func: Callable[[Node, List[Node]], List[Node]]):
        """Set the function that determines neighborhoods"""
        self.neighborhood_function = func

    def get_neighbors(self, node: Node) -> List[Node]:
        """Get neighbors for a node using the neighborhood function"""
        return self.neighborhood_function(node, list(self.nodes.values()))

    @staticmethod
    def no_neighbors(
            node: Node,  # pylint: disable=unused-argument
            all_node: List[Node]  # pylint: disable=unused-argument
    ) -> List[Node]:
        """Default neighborhood function (no neighbors)"""
        return []


class Event:
    """
    A class to represent an event in the simulation.
    An event has a time, an action (function), and optional arguments.
    """

    def __init__(self, time: float, action: Callable[..., None], *args, **kwargs):
        self.time = time
        self.action = action
        self.args = args
        self.kwargs = kwargs

    def execute(self):
        """Execute the event's action"""
        return self.action(*self.args, **self.kwargs)

    def __lt__(self, other):
        """For priority queue ordering"""
        return self.time < other.time


class Simulator:
    """
    A class to represent the simulator for a simple aggregate computing system.
    """
    def __init__(self):
        self.event_queue = []
        self.current_time = 0.0
        self.running = False
        self.environment = Environment()

    def schedule_event(
        self, time_delta: float, action: Callable[..., None], *args, **kwargs
    ):
        """Schedule an event to occur after time_delta"""
        event_time = self.current_time + time_delta
        event = Event(event_time, action, *args, **kwargs)
        heapq.heappush(self.event_queue, event)
        return event

    def run(self, until_time: Optional[float] = None):
        """Run the simulation until the specified time or until no more events"""
        self.running = True

        while self.running and self.event_queue:
            event = heapq.heappop(self.event_queue)

            if until_time is not None and event.time > until_time:
                heapq.heappush(self.event_queue, event)  # Put the event back
                break

            self.current_time = event.time
            event.execute()

        self.running = False

    def stop(self):
        """Stop the simulation"""
        self.running = False

    def cancel_event(self, event: Event):
        """Cancel a scheduled event"""
        if event in self.event_queue:
            self.event_queue.remove(event)
            heapq.heapify(self.event_queue)
        else:
            raise ValueError("Event not found in the queue")

    def reset(self):
        """Reset the simulator"""
        self.event_queue = []
        self.current_time = 0.0
        self.running = False
        self.environment = Environment()

    def create_node(
        self, position: Tuple[float, ...], data: Any = None, node_id=None
    ) -> Node:
        """Helper method to create and add a node to the environment"""
        node = Node(position, data, node_id)
        self.environment.add_node(node)
        return node

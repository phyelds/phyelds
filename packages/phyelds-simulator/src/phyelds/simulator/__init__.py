"""
A simple simulator for aggregate computing systems in phyelds.
This simulator allows you to create nodes, set their positions and data,
and define their neighborhoods.
It also provides a way to schedule events and run the simulation.
"""

from abc import ABC
import heapq
import uuid
from typing import Dict, Callable, Any, Optional, Protocol, Tuple, List


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
        self.environment = None
        self.position = position
        if data is None:
            data = {}
        self.data = data

    @property
    def position(self) -> Tuple[float, ...]:
        """Where the node is; setting it keeps the spatial indexes of its environment up to date."""
        return self._position

    @position.setter
    def position(self, position: Tuple[float, ...]) -> None:
        old_position = getattr(self, "_position", None)
        self._position = position
        if self.environment is not None:
            self.environment.node_moved(self, old_position)

    def update(
        self, new_position: Optional[Tuple[float, ...]] = None, new_data: Any = None
    ):
        """Update node position and/or data"""
        if new_position is not None:
            self.position = new_position
        if new_data is not None:
            self.data = new_data

    def get_neighbors(self):
        """Get neighboring nodes from the environment"""
        if self.environment:
            return self.environment.get_neighbors(self)
        return []

    def __eq__(self, other):
        """Define equality based on node id"""
        if not isinstance(other, Node):
            return False
        return self.id == other.id

    def __hash__(self):
        """Hash based on node id"""
        return hash(self.id)

    def __str__(self):
        return f"Node(id={self.id}, position={self.position}, data={self.data})"


class SpatialIndex(Protocol):
    """An index of the nodes of an environment by their position, which it keeps up to date."""

    def __len__(self) -> int:
        """How many nodes the index holds."""

    def added(self, node: Node, replaced: Optional[Node]) -> None:
        """Index ``node``, in place of ``replaced``: the node it replaced, with the same id."""

    def removed(self, node: Node) -> None:
        """Forget ``node``."""

    def moved(self, node: Node, old_position: Tuple[float, ...]) -> None:
        """Index ``node`` at its position, no longer at ``old_position``."""


class Environment:
    """
    A class to represent the environment in which nodes exist.
    It manages the nodes and their neighborhoods.
    It also provides a way to set the neighborhood function.
    """

    def __init__(
        self, neighborhood_function: Callable[[Node, "Environment"], List[Node]] = None
    ):
        self.nodes: Dict[any, Node] = {}
        self.neighborhood_function = neighborhood_function or self.no_neighbors
        self._indexes: Dict[Any, SpatialIndex] = {}

    def add_data_for_all_nodes(self, data: Dict[str, Any]):
        """Add data to all nodes in the environment"""
        for node in self.nodes.values():
            node.data.update(data)

    def node_list(self) -> List[Node]:
        """Return a list of all nodes in the environment"""
        return list(self.nodes.values())

    def add_node(self, node: Node):
        """Add a node to the environment"""
        replaced = self.nodes.get(node.id)
        self.nodes[node.id] = node
        node.environment = self
        for index in self._indexes.values():
            index.added(node, replaced)

    def remove_node(self, node_id: str):
        """Remove a node from the environment"""
        if node_id in self.nodes:
            node = self.nodes.pop(node_id)
            node.environment = None
            for index in self._indexes.values():
                index.removed(node)

    def node_moved(self, node: Node, old_position: Tuple[float, ...]) -> None:
        """
        Keep the spatial indexes up to date: a node calls it when its position changes.

        Args:
            node: The node that moved.
            old_position: Where it was.
        """
        for index in self._indexes.values():
            index.moved(node, old_position)

    def spatial_index(self, key: Any, build: Callable[[List[Node]], SpatialIndex]) -> SpatialIndex:
        """
        The spatial index of ``key``, built on the first request and then kept up to date.

        Args:
            key: What the index is, e.g. the kind and size of its cells.
            build: How to build the index from the nodes.

        Returns:
            The index, rebuilt if nodes were added or removed other than with ``add_node``
            and ``remove_node``.
        """
        index = self._indexes.get(key)
        if index is None or len(index) != len(self.nodes):
            index = self._indexes[key] = build(self.node_list())
        return index

    def set_neighborhood_function(self, func: Callable[[Node, "Environment"], List[Node]]):
        """Set the function that determines neighborhoods"""
        self.neighborhood_function = func

    def get_neighbors(self, node: Node) -> List[Node]:
        """Get neighbors for a node using the neighborhood function"""
        return self.neighborhood_function(node, self)

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

    def __str__(self):
        return f"Event(time={self.time}, action={self.action.__name__})"

    def __repr__(self):
        return self.__str__()


class Monitor(ABC):
    """
    An abstract base class for monitors that can observe the simulation.
    """
    def __init__(self, simulator):
        self.simulator = simulator
        self.simulator.add_monitor(monitor=self)

    def on_start(self) -> None:
        """Called when the simulation starts"""

    def on_finish(self) -> None:
        """Called when the simulation finishes"""

    def update(self) -> None:
        """Called after each event execution"""


class Simulator:
    """
    A class to represent the simulator for a simple aggregate computing system.
    """
    def __init__(self, environment: Environment = None):
        self.event_queue = []
        self.current_time = 0.0
        self.running = False
        if environment is None:
            self.environment = Environment()
        else:
            self.environment = environment
        self.monitors = []

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

        for monitor in self.monitors:
            monitor.on_start()

        while self.running and self.event_queue:
            event = heapq.heappop(self.event_queue)
            if until_time is not None and event.time > until_time:
                heapq.heappush(self.event_queue, event)  # Put the event back
                break

            self.current_time = event.time
            event.execute()

            for monitor in self.monitors:
                monitor.update()

        self.running = False

        for monitor in self.monitors:
            monitor.on_finish()

    def continue_run(self, until_time: Optional[float] = None):
        """Continue running the simulation until the specified time or until no more events"""
        if self.running:
            return  # Already running
        self.run(self.current_time + until_time)

    def add_monitor(self, monitor: Monitor) -> None:
        """Add a monitor to the simulator"""
        self.monitors.append(monitor)

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

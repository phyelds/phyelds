"""
Engine interface: how to implement an aggregate computing engine.
"""
from abc import ABC
from dataclasses import dataclass
from typing import List, Dict, Any


class NodeContext(ABC):
    """
    Abstract base class for the node context. This class should be implemented by the user.
    """

    def __init__(
            self, node_id: int, sensors: dict[str, any] = None, outputs: dict[str, any] = None
    ):
        """
        Create the context of a device.

        Args:
            node_id: The ID of the device.
            sensors: The sensors of the device, mapping each name to its value.
            outputs: The outputs of the device, mapping each name to its value;
                empty by default.
        """
        self.node_id = node_id
        self.sensors = sensors  # map sensor name to sensor value
        if outputs is None:
            outputs = {}
        self.outputs = outputs

    def sense(self, sensor_name: str) -> any:
        """
        Read a sensor of the device.

        Args:
            sensor_name: The name of the sensor.

        Returns:
            The value of the sensor, or ``None`` if the device has no such sensor.
        """
        return self.sensors.get(sensor_name)

    def store(self, output_name: str, value: any) -> None:
        """
        Write an output of the device, replacing its previous value.

        Args:
            output_name: The name of the output.
            value: The value to store.
        """
        if self.outputs is None:
            self.outputs = {}
        self.outputs[output_name] = value

    def position(self) -> any:
        """
        Return the position of the device.

        Returns:
            The value of the ``"position"`` sensor, or ``None`` if there is none.
        """
        return self.sensors.get("position")

    def time(self) -> float:
        """
        Return the time of the current round, as perceived by the device.

        Returns:
            The value of the ``"time"`` sensor, or ``None`` if there is none.
        """
        return self.sensors.get("time")


@dataclass
class EngineState:
    """
    Inner state of the engine used to process aggregate computation.
    """
    stack: List[str] = None
    state_trace: Dict[str, Any] = None
    count_stack: List[int] = None
    to_send: Dict[str, Any] = None
    messages: Dict[int, Dict[str, Any]] = None
    node_id: int = 0
    reads: set = None

    def __post_init__(self):
        self.stack = [] if self.stack is None else self.stack
        self.state_trace = {} if self.state_trace is None else self.state_trace
        self.count_stack = [0] if self.count_stack is None else self.count_stack
        self.to_send = {} if self.to_send is None else self.to_send
        self.messages = {} if self.messages is None else self.messages
        self.reads = set() if self.reads is None else self.reads


class Engine(ABC):
    """
    Abstract base class for the engine. This class should be implemented by the user.
    """

    def __init__(self):
        self.node_context: NodeContext | None = None
        self.engine_state: EngineState | None = None

    def setup(
        self, node_context: NodeContext, messages: dict[int, dict[str, any]], state=None
    ) -> "Engine":
        """
        Prepare the engine for a round of the device.

        Args:
            node_context: The context of the device running the round.
            messages: The messages received from the neighbors, mapping each neighbor
                ID to the values it sent, keyed by alignment path.
            state (dict[str, Any] | None): The state left by the previous round (see
                ``state_trace``), or ``None`` on the first round.

        Returns:
            The engine itself.
        """

    def enter(self, name: str) -> None:
        """
        Enter a new alignment point, nested in the current one.

        Args:
            name: The name of the alignment point.
        """

    def exit(self) -> None:
        """
        Leave the current alignment point, going back to the enclosing one.
        """

    def current_path(self) -> list[str]:
        """
        Return the current alignment path.

        Returns:
            A copy of the alignment points entered so far, outermost first.
        """

    def write_state(self, value: any, stack: list[str]) -> None:
        """
        Store a value of the device's state, to be read in the next rounds.

        Args:
            value: The value to store.
            stack: The alignment path the value belongs to.
        """

    def read_state(self, stack: list[str]) -> any:
        """
        Read a value of the device's state, marking it as still in use.

        Args:
            stack: The alignment path the value belongs to.

        Returns:
            The stored value, or ``None`` if there is none.
        """

    def state_trace(self) -> dict[str, any]:
        """
        Return the state of the device, to pass to ``setup`` in the next round.

        Returns:
            A copy of the stored values, keyed by alignment path.
        """

    def forget(self, _self_path):
        """
        Remove a value from the device's state.

        Args:
            _self_path (list[str]): The alignment path of the value to remove.
        """

    def send(self, data: any, stack: list[str] | None = None) -> None:
        """
        Queue a value to send to the neighbors at the end of the round.

        Args:
            data: The value to send.
            stack: The alignment path to send it at; the current one by default.
        """

    def aligned(self) -> list[int]:
        """
        Return the neighbors aligned with the current alignment point.

        Returns:
            The IDs of the neighbors that sent a value at the current alignment path.
        """

    def aligned_values(self, path: list[str]) -> dict[int, any]:
        """
        Return the values the aligned neighbors sent at ``path``.

        Args:
            path: The alignment path of the values.

        Returns:
            A dictionary mapping each neighbor ID to the value it sent at ``path``.
        """

    def cooldown(self) -> dict[str, Any]:
        """
        End the round: drop the state not read in it and collect the outgoing messages.

        Returns:
            The values to send to the neighbors, keyed by alignment path.
        """

"""
Engine interface: how to implement an aggregate computing engine.
"""
from abc import ABC
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from phyelds.data import NeighborhoodField

# The default of a neighbor field when none is given: the value of the device itself.
_LOCAL = object()


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
    stack: List[Any] = None
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

    Attributes:
        vectorized: Whether the engine runs many devices at once, each value holding one per
            device: ``@aggregate`` then rewrites the ``if`` statements, the conditional
            expressions, ``and``, ``or``, ``not``, ``min`` and ``max`` into ``branch`` and
            ``choose``, which run each side for the devices choosing it. ``False`` by
            default: one device, plain Python.
    """

    vectorized: bool = False

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
        raise NotImplementedError

    def enter(self, name: str) -> None:
        """
        Enter a new alignment point, nested in the current one.

        Args:
            name: The name of the alignment point.
        """
        raise NotImplementedError

    def exit(self) -> None:
        """
        Leave the current alignment point, going back to the enclosing one.
        """
        raise NotImplementedError

    def branch(
        self, condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]
    ) -> Any:
        """
        Run the branch of a conditional that ``condition`` chooses, in its own alignment point.

        ``if_true`` runs in ``"left"`` and ``if_false`` in ``"right"``, as ``align_left`` and
        ``align_right`` do, so devices on different branches do not exchange values. A batch
        engine, running many devices at once, runs each branch for the devices choosing it.

        Args:
            condition: What chooses the branch: ``if_true`` if it is truthy.
            if_true: The branch for a truthy ``condition``.
            if_false: The branch for a falsy ``condition``.

        Returns:
            What the branch returns.
        """
        chosen, side = (if_true, "left") if condition else (if_false, "right")
        self.enter(side)
        try:
            return chosen()
        finally:
            self.exit()

    def choose(
        self, condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]
    ) -> Any:
        """
        Run the side of a choice that ``condition`` picks, without an alignment point.

        A batch engine, running many devices at once, runs each side for the devices
        picking it.

        Args:
            condition: What picks the side: ``if_true`` if it is truthy.
            if_true: The side for a truthy ``condition``.
            if_false: The side for a falsy ``condition``.

        Returns:
            What the side returns.
        """
        return if_true() if condition else if_false()

    def current_path(self) -> list:
        """
        Return the current alignment path.

        Returns:
            A copy of the segments of the alignment points entered so far, outermost
            first, as the engine encodes them: pass it back to the other methods.
        """
        raise NotImplementedError

    def write_state(self, value: any, stack: list | None = None) -> None:
        """
        Store a value of the device's state, to be read in the next rounds.

        Args:
            value: The value to store.
            stack: The alignment path the value belongs to; the current one by default.
        """
        raise NotImplementedError

    def read_state(self, stack: list | None = None) -> any:
        """
        Read a value of the device's state, marking it as still in use.

        Args:
            stack: The alignment path the value belongs to; the current one by default.

        Returns:
            The stored value, or ``None`` if there is none.
        """
        raise NotImplementedError

    def read_state_or(self, init: Any, stack: list | None = None) -> Any:
        """
        Read a value of the device's state, storing ``init`` first if there is none.

        A batch engine, running many devices at once, reads or stores each one's value.

        Args:
            init: The value to store, and return, if the state has none at ``stack``.
            stack: The alignment path the value belongs to; the current one by default.

        Returns:
            The stored value, or ``init``.
        """
        stored = self.read_state(stack)
        if stored is None:
            self.write_state(init, stack)
            return init
        return stored

    def state_trace(self) -> dict[str, any]:
        """
        Return the state of the device, to pass to ``setup`` in the next round.

        Returns:
            A copy of the stored values, keyed by alignment path.
        """
        raise NotImplementedError

    def forget(self, _self_path):
        """
        Remove a value from the device's state.

        Args:
            _self_path (list): The alignment path of the value to remove.
        """
        raise NotImplementedError

    def send(self, data: any, stack: list | None = None) -> None:
        """
        Queue a value to send to the neighbors at the end of the round.

        Args:
            data: The value to send.
            stack: The alignment path to send it at; the current one by default.
        """
        raise NotImplementedError

    def aligned(self) -> list[int]:
        """
        Return the neighbors aligned with the current alignment point.

        Returns:
            The IDs of the neighbors that sent a value at the current alignment path.
        """
        raise NotImplementedError

    def aligned_values(self, path: list | None = None) -> dict[int, any]:
        """
        Return the values the aligned neighbors sent at ``path``.

        Args:
            path: The alignment path of the values; the current one by default.

        Returns:
            A dictionary mapping each neighbor ID to the value it sent at ``path``.
        """
        raise NotImplementedError

    def neighbor_field(
        self,
        local: Any,
        path: list | None = None,
        default: Any = _LOCAL,
        *,
        addressed: bool = False,
    ) -> NeighborhoodField:
        """
        Return the field of the values the aligned neighbors sent at ``path``, and ``local``.

        A batch engine, running many devices at once, returns one field for all of them.

        Args:
            local: The value of the device itself.
            path: The alignment path of the values; the current one by default.
            default: The value of the field for the devices it does not hold; ``local`` by
                default.
            addressed: Whether a neighbor may have sent a field, addressing each device its
                own value, as ``exchange`` does: the device then takes the value addressed
                to it.

        Returns:
            A ``NeighborhoodField`` mapping the device to ``local`` and each aligned
                neighbor to what it sent.
        """
        node_id = self.node_context.node_id
        values = self.aligned_values(path)
        if addressed:
            values = {
                sender: value.for_node(node_id) if isinstance(value, NeighborhoodField) else value
                for sender, value in values.items()
            }
        values[node_id] = local
        if default is _LOCAL:
            return NeighborhoodField(values, node_id)
        return NeighborhoodField(values, node_id, default=default)

    def begin_process(self, name: str) -> Any:
        """
        Enter an isolated alignment point for a process key, saving current round effects.

        Args:
            name: The process alignment segment name.

        Returns:
            An opaque checkpoint token for ``end_process``.
        """
        raise NotImplementedError

    def end_process(self, token: Any, commit: bool) -> None:
        """
        Leave a process alignment point, committing or rolling back its round effects.

        Args:
            token: The checkpoint token returned by ``begin_process``.
            commit: True to keep state and outgoing messages, False to restore ``token``.
        """
        raise NotImplementedError

    def cooldown(self) -> dict[str, Any]:
        """
        End the round: drop the state not read in it and collect the outgoing messages.

        Returns:
            The values to send to the neighbors, keyed by alignment path.
        """
        raise NotImplementedError

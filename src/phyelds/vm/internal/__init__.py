"""
Engine is the core of the phyelds library. It manages the state and message passing
between different contexts. It provides methods to enter and exit contexts, send messages,
and manage the state of the system.
"""

from typing import Dict, List, Any, Optional

from phyelds.vm import Engine, NodeContext, EngineState


class DebugPaths:
    """Readable paths: segments such as ``"neighbors@1"``, keyed by ``str`` of the path."""

    def segment(self, parent: Any, name: Any, counter: int) -> str:
        """
        The segment of an alignment point.

        Args:
            parent: The segment above it, ``None`` at the top; unused.
            name: The name of the point: a function, a branch, or a key given to ``align``.
            counter: How many points the parent entered before this one.

        Returns:
            ``"name@counter"``.
        """
        del parent
        return f"{name}@{counter}"

    def key(self, path: List[Any]) -> str:
        """The key of ``path``, a list of segments: ``str`` of it."""
        return str(path)


# Two hashes, each below a prime under 2**15: their products stay small integers on 32-bit
# MicroPython boards (under 2**30), which would otherwise allocate each one on the heap.
_HIGH, _LOW = 32749, 32719
_ROOT = 1 << 15 | 1


class CompactPaths:
    """
    Compact paths: each segment is the 30-bit key of the path up to it, built on the segment
    above, so that the key of a path is its last segment. The key is the same on every
    runtime (unlike ``hash``, which is salted), and a small integer on 32-bit MicroPython
    boards.
    """

    def segment(self, parent: Any, name: Any, counter: int) -> int:
        """
        The segment of an alignment point: two polynomial hashes of the bytes of ``name``
        and of ``counter``, on from those of ``parent``.

        Args:
            parent: The segment above it, ``None`` at the top.
            name: The name of the point: a function, a branch, or a key given to ``align``,
                hashed as ``str`` writes it.
            counter: How many points the parent entered before this one.

        Returns:
            The key of the path up to this point.
        """
        # ponytail: 30-bit keys, ~1e-3 chance of a collision with 1000 paths; widen if needed
        start = _ROOT if parent is None else parent
        high, low = start >> 15, start & 0x7FFF
        for byte in str(name).encode():
            high = (high * 31 + byte) % _HIGH
            low = (low * 37 + byte) % _LOW
        high = (high * 31 + 256 + counter) % _HIGH  # above any byte: it closes the segment
        low = (low * 37 + 256 + counter) % _LOW
        return high << 15 | low

    def key(self, path: List[Any]) -> int:
        """The key of ``path``, a list of segments: its last one."""
        return path[-1] if path else _ROOT


_PATHS = {"debug": DebugPaths(), "compact": CompactPaths()}


class MutableEngine(Engine):
    """
    MutableEngine is the responsible for managing the state and message passing
    in an aggregate computing system. It provides methods to enter and exit contexts,
    send messages, and manage the state of the system.

    Args:
        paths: How alignment paths become state and message keys. ``"debug"`` (the
            default, ``DebugPaths``) keeps them readable, as strings; ``"compact"``
            (``CompactPaths``) turns them into small integers, lighter for microcontrollers
            and their radios. Any other encoding is an object with the methods of those:
            ``segment(parent, name, counter)`` encodes an alignment point as it is entered,
            ``key(path)`` turns a list of segments into a hashable key. Devices that talk
            to each other must use the same encoding.

    Raises:
        ValueError: If ``paths`` is a string other than ``"debug"`` and ``"compact"``.
    """
    def __init__(self, paths: Any = "debug"):
        super().__init__()
        if isinstance(paths, str):
            if paths not in _PATHS:
                raise ValueError(
                    f"paths must be one of {sorted(_PATHS)} or an encoding, not {paths!r}"
                )
            paths = _PATHS[paths]
        self._segment = paths.segment
        self._key = paths.key
        self.engine_state = EngineState()

    def setup(
        self, node_context: NodeContext, messages=None, state=None
    ) -> Engine:
        if messages is None:
            messages = {}
        if state is None:
            state = {}
        self.node_context = node_context
        self.engine_state = EngineState(
            stack=[],
            state_trace=state.copy(),  # Copy the state to avoid modifying the original
            count_stack=[0],  # Reset counter stack
            to_send={},
            messages=messages,
            node_id=node_context.node_id,
            reads=set(),
        )
        return self

    def enter(self, name: str) -> None:
        counter: int = self.engine_state.count_stack[-1]
        self.engine_state.count_stack[-1] += 1
        stack = self.engine_state.stack
        stack.append(self._segment(stack[-1] if stack else None, name, counter))
        self.engine_state.count_stack.append(0)

    def forget(self, stack: List[Any]) -> None:
        key = self._key(stack)
        if key in self.engine_state.state_trace:
            del self.engine_state.state_trace[key]

    def exit(self) -> None:
        if self.engine_state.stack:
            self.engine_state.stack.pop()
            self.engine_state.count_stack.pop()

    def current_path(self) -> list:
        return self.engine_state.stack.copy()

    def write_state(self, value: Any, stack: List[Any]) -> None:
        self.engine_state.state_trace[self._key(stack)] = value

    def read_state(self, stack: List[Any]) -> Optional[Any]:
        key = self._key(stack)
        self.engine_state.reads.add(key)
        return self.engine_state.state_trace.get(key)

    def send(self, data: Any, stack: Optional[List[Any]] = None) -> None:
        target_stack = self.engine_state.stack if stack is None else stack
        self.engine_state.to_send[self._key(target_stack)] = data

    def aligned(self) -> List[int]:
        key = self._key(self.engine_state.stack)
        return [
            node_id for node_id, messages in self.engine_state.messages.items() if key in messages
        ]

    def aligned_values(self, path: List[Any]) -> Dict[int, Any]:
        key = self._key(path)
        messages = self.engine_state.messages
        return {
            node_id: messages[node_id][key]
            for node_id in self.aligned()
            if key in messages[node_id]
        }

    def state_trace(self) -> Dict[str, Any]:
        """
        Get the state trace of the engine.
        :return: The state trace.
        """
        return self.engine_state.state_trace.copy()

    def cooldown(self) -> Dict[str, Any]:
        flatten_messages: Dict[str, Any] = {}
        for key in self.engine_state.to_send:
            value = self.engine_state.to_send[key]
            flatten_messages[key] = value
        # get state that were not read
        for key in self.engine_state.state_trace.copy():
            if key not in self.engine_state.reads:
                del self.engine_state.state_trace[key]
        self.engine_state.to_send = {}
        self.engine_state.stack = []
        self.engine_state.count_stack = []  # Reset counter stack
        self.engine_state.messages = {}
        return flatten_messages

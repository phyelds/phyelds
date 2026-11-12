"""
Engine is the core of the phyelds library. It manages the state and message passing
between different contexts. It provides methods to enter and exit contexts, send messages,
and manage the state of the system.
"""

import sys
from typing import Any, Dict, List, Optional

from phyelds.vm import Engine, EngineState, NodeContext

_IS_MICROPYTHON = sys.implementation.name == "micropython"
_MAX_SEGMENT_CACHE = 4096


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

    def __init__(self) -> None:
        self._cache: Optional[Dict[Any, int]] = None if _IS_MICROPYTHON else {}

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
        cache = self._cache
        if cache is not None:
            normalized = name if isinstance(name, (str, int)) else str(name)
            cache_key = (parent, normalized, counter)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        start = _ROOT if parent is None else parent
        high, low = start >> 15, start & 0x7FFF
        for byte in str(name).encode():
            high = (high * 31 + byte) % _HIGH
            low = (low * 37 + byte) % _LOW
        high = (high * 31 + 256 + counter) % _HIGH  # above any byte: it closes the segment
        low = (low * 37 + 256 + counter) % _LOW
        result = high << 15 | low
        if cache is not None:
            if len(cache) >= _MAX_SEGMENT_CACHE:
                cache.clear()
            cache[cache_key] = result
        return result

    def key(self, path: List[Any]) -> int:
        """The key of ``path``, a list of segments: its last one."""
        return path[-1] if path else _ROOT


_DEBUG_PATHS = DebugPaths()
_COMPACT_PATHS = CompactPaths() if _IS_MICROPYTHON else None


class MutableEngine(Engine):
    """
    MutableEngine is responsible for managing the state and message passing
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
            if paths == "debug":
                paths = _DEBUG_PATHS
            elif paths == "compact":
                paths = _COMPACT_PATHS if _COMPACT_PATHS is not None else CompactPaths()
            else:
                raise ValueError(
                    f"paths must be one of ['compact', 'debug'] or an encoding, not {paths!r}"
                )
        self._segment = paths.segment
        self._key = paths.key
        self.engine_state: Optional[EngineState] = None

    def setup(
        self, node_context: NodeContext, messages=None, state=None
    ) -> Engine:
        if messages is None:
            messages = {}
        state_copy = {} if state is None else state.copy()
        self.node_context = node_context
        current = self.engine_state
        if current is None:
            self.engine_state = EngineState(
                stack=[],
                state_trace=state_copy,
                count_stack=[0],
                to_send={},
                messages=messages,
                node_id=node_context.node_id,
                reads=set(),
            )
        else:
            current.stack.clear()
            current.state_trace = state_copy
            current.count_stack.clear()
            current.count_stack.append(0)
            current.to_send = {}
            current.messages = messages
            current.node_id = node_context.node_id
            current.reads.clear()
        return self

    def enter(self, name: str) -> None:
        state = self.engine_state
        count_stack = state.count_stack
        counter: int = count_stack[-1]
        count_stack[-1] = counter + 1
        stack = state.stack
        stack.append(self._segment(stack[-1] if stack else None, name, counter))
        count_stack.append(0)

    def key(self, path: List[Any]) -> Any:
        """
        The state and message key of ``path``, as the encoding of the engine makes it.

        Args:
            path: A list of segments, as ``current_path`` returns it.

        Returns:
            The key.
        """
        return self._key(path)

    def forget(self, stack: List[Any]) -> None:
        key = self._key(stack)
        if key in self.engine_state.state_trace:
            del self.engine_state.state_trace[key]

    def exit(self) -> None:
        state = self.engine_state
        if state.stack:
            state.stack.pop()
            state.count_stack.pop()

    def current_path(self) -> list:
        return self.engine_state.stack.copy()

    def write_state(self, value: Any, stack: Optional[List[Any]] = None) -> None:
        state = self.engine_state
        target = state.stack if stack is None else stack
        state.state_trace[self._key(target)] = value

    def read_state(self, stack: Optional[List[Any]] = None) -> Optional[Any]:
        state = self.engine_state
        target = state.stack if stack is None else stack
        key = self._key(target)
        state.reads.add(key)
        return state.state_trace.get(key)

    def send(self, data: Any, stack: Optional[List[Any]] = None) -> None:
        state = self.engine_state
        target_stack = state.stack if stack is None else stack
        state.to_send[self._key(target_stack)] = data

    def aligned(self) -> List[int]:
        state = self.engine_state
        key = self._key(state.stack)
        return [
            node_id for node_id, messages in state.messages.items() if key in messages
        ]

    def aligned_values(self, path: Optional[List[Any]] = None) -> Dict[int, Any]:
        state = self.engine_state
        current_key = self._key(state.stack)
        messages = state.messages
        if path is None:
            return {
                node_id: peer_msgs[current_key]
                for node_id, peer_msgs in messages.items()
                if current_key in peer_msgs
            }
        key = self._key(path)
        if key == current_key:
            return {
                node_id: peer_msgs[key]
                for node_id, peer_msgs in messages.items()
                if key in peer_msgs
            }
        return {
            node_id: peer_msgs[key]
            for node_id, peer_msgs in messages.items()
            if current_key in peer_msgs and key in peer_msgs
        }

    def begin_process(self, name: str) -> Any:
        state = self.engine_state
        saved = (state.to_send.copy(), state.state_trace.copy(), state.reads.copy())
        counter = state.count_stack[-1]
        state.count_stack[-1] = 0
        self.enter(name)
        state.count_stack[-2] = counter
        return saved

    def end_process(self, token: Any, commit: bool) -> None:
        self.exit()
        if not commit:
            state = self.engine_state
            state.to_send, state.state_trace, state.reads = token

    def state_trace(self) -> Dict[str, Any]:
        """
        Get the state trace of the engine.

        Returns:
            A copy of the state trace.
        """
        return self.engine_state.state_trace.copy()

    def cooldown(self) -> Dict[str, Any]:
        state = self.engine_state
        flatten_messages: Dict[str, Any] = state.to_send
        reads = state.reads
        state_trace = state.state_trace
        dead = [key for key in state_trace if key not in reads]
        for key in dead:
            del state_trace[key]
        state.to_send = {}
        state.stack.clear()
        state.count_stack.clear()
        state.messages = {}
        return flatten_messages

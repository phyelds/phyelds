"""
Engine is the core of the phyelds library. It manages the state and message passing
between different contexts. It provides methods to enter and exit contexts, send messages,
and manage the state of the system.
"""

from typing import Callable, Dict, List, Any, Optional, Union

from phyelds.vm import Engine, NodeContext, EngineState

_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193
_SLASH = ord("/")


def _extend_digest(digest: int, segment: Any) -> int:
    """
    The FNV-1a hash ``digest`` of a path, followed by ``segment`` (a name or a number, as
    ``str`` writes it) and a slash.
    """
    for byte in str(segment).encode():
        digest = ((digest ^ byte) * _FNV_PRIME) & 0xFFFFFFFF
    return ((digest ^ _SLASH) * _FNV_PRIME) & 0xFFFFFFFF


class _CompactKeys:  # pylint: disable=too-few-public-methods
    """
    The compact key of a path: its FNV-1a hash, the same on every runtime (unlike ``hash``,
    which is salted), cut to 30 bits so that it stays a small integer on 32-bit MicroPython
    boards, which would otherwise allocate a big integer for each key.

    The hash of a path goes on from that of the start it shares with the last path hashed:
    the paths of a round come one after the other in the program, and share most of it.
    """

    def __init__(self):
        self._hashed: List[str] = []
        self._hashes: List[int] = [_FNV_OFFSET]

    def __call__(self, path: List[str]) -> int:
        hashed, hashes = self._hashed, self._hashes
        shared = 0
        limit = min(len(path), len(hashed))
        while shared < limit and path[shared] == hashed[shared]:
            shared += 1
        while len(hashed) > shared:
            hashed.pop()
            hashes.pop()
        for index in range(shared, len(path)):
            hashed.append(path[index])
            hashes.append(_extend_digest(hashes[-1], path[index]))
        # ponytail: 30-bit keys, ~1e-3 chance of a collision with 1000 paths; widen if needed
        return hashes[-1] & 0x3FFFFFFF


# Debug keys are str(path): built whole, in C, they are faster than from a shared start.
_PATH_KEYS = {"debug": lambda: str, "compact": _CompactKeys}


class MutableEngine(Engine):
    """
    MutableEngine is the responsible for managing the state and message passing
    in an aggregate computing system. It provides methods to enter and exit contexts,
    send messages, and manage the state of the system.

    Args:
        paths: How alignment paths become state and message keys. ``"debug"`` (the
            default) keeps them readable, as strings; ``"compact"`` turns them into
            small integers, lighter for microcontrollers and their radios. Any other
            encoding is a function from a path (a list of segments, such as
            ``"neighbors@1"``) to a hashable key, e.g. a tuple of numbers. Devices that
            talk to each other must use the same encoding.

    Raises:
        ValueError: If ``paths`` is neither ``"debug"``, ``"compact"`` nor a function.
    """
    def __init__(self, paths: Union[str, Callable[[List[Any]], Any]] = "debug"):
        super().__init__()
        if callable(paths):
            self._key = paths
        elif paths in _PATH_KEYS:
            self._key = _PATH_KEYS[paths]()
        else:
            raise ValueError(
                f"paths must be one of {sorted(_PATH_KEYS)} or a function, not {paths!r}"
            )
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
        self.engine_state.stack.append(f"{name}@{counter}")
        self.engine_state.count_stack.append(0)

    def forget(self, stack: List[str]) -> None:
        key = self._key(stack)
        if key in self.engine_state.state_trace:
            del self.engine_state.state_trace[key]

    def exit(self) -> None:
        if self.engine_state.stack:
            self.engine_state.stack.pop()
            self.engine_state.count_stack.pop()

    def current_path(self) -> list[str]:
        return self.engine_state.stack.copy()

    def write_state(self, value: Any, stack: List[str]) -> None:
        self.engine_state.state_trace[self._key(stack)] = value

    def read_state(self, stack: List[str]) -> Optional[Any]:
        key = self._key(stack)
        self.engine_state.reads.add(key)
        return self.engine_state.state_trace.get(key)

    def send(self, data: Any, stack: Optional[List[str]] = None) -> None:
        target_stack = self.engine_state.stack if stack is None else stack
        self.engine_state.to_send[self._key(target_stack)] = data

    def aligned(self) -> List[int]:
        key = self._key(self.engine_state.stack)
        return [
            node_id for node_id, messages in self.engine_state.messages.items() if key in messages
        ]

    def aligned_values(self, path: List[str]) -> Dict[int, Any]:
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

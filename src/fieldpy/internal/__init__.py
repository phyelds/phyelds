"""
Engine is the core of the FieldPy library. It manages the state and message passing
between different contexts. It provides methods to enter and exit contexts, send messages,
and manage the state of the system.
"""

from typing import Dict, List, Any, Optional
from fieldpy.abstractions import Engine


class MutableEngine(Engine):
    def __init__(self):
        self.stack: List[str] = []
        self.state: Dict[str, Any] = {}
        self.count_stack: List[int] = [0]
        self.to_send: Dict[str, Any] = {}
        self.messages: Dict[int, Dict[str, Any]] = {}
        self.count: int = 0
        self.id: int = 0
        self.reads = set()

    def setup(self, messages: Dict[int, Dict[str, Any]], id: int, state=None) -> None:
        if state is None:
            state = {}
        self.stack: List[str] = []
        self.state: Dict[str, Any] = (
            state.copy()
        )  # Copy the state to avoid modifying the original
        self.count_stack: List[int] = [0]  # Reset counter stack
        self.to_send: Dict[str, Any] = {}
        self.messages: Dict[int, Dict[str, Any]] = messages
        self.count: int = 0  # Reset global counter
        self.id: int = id
        self.reads = set()

    def enter(self, name: str) -> None:
        counter: int = self.count_stack[-1]
        self.count_stack[-1] += 1
        self.stack.append(f"{name}@{counter}")
        self.count_stack.append(0)

    def forget(self, stack: List[str]) -> None:
        if str(stack) in self.state:
            del self.state[str(stack)]

    def write_state(self, value: Any, stack: List[str]) -> None:
        self.state[str(stack)] = value

    def read_state(self, stack: List[str]) -> Optional[Any]:
        self.reads.add(str(stack))
        return self.state.get(str(stack))

    def exit(self) -> None:
        if self.stack:
            self.stack.pop()
            self.count_stack.pop()

    def send(self, data: Any) -> None:
        self.to_send[str(self.stack)] = data

    def aligned(self) -> List[int]:
        aligned: List[int] = []
        for id in self.messages:
            if str(self.stack) in self.messages[id]:
                aligned.append(id)

        return aligned

    def aligned_values(self, path: List[str]) -> Dict[int, Any]:
        aligned: List[int] = self.aligned()
        path_str: str = str(path)
        aligned_values: Dict[int, Any] = {}
        # take the values of the given path
        for id in aligned:
            if path_str in self.messages[id]:
                aligned_values[id] = self.messages[id][path_str]
        return aligned_values

    def cooldown(self) -> Dict[str, Any]:
        flatten_messages: Dict[str, Any] = {}
        for key in self.to_send:
            value = self.to_send[key]
            flatten_messages[key] = value
        # get state that were not read
        for key in self.state.copy():
            if key not in self.reads:
                del self.state[key]
        self.to_send = {}
        self.stack = []
        self.count_stack = []  # Reset counter stack
        self.count = 0  # Reset global counter
        self.messages = []
        return flatten_messages

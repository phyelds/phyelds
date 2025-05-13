"""
Engine is the core of the phyelds library. It manages the state and message passing
between different contexts. It provides methods to enter and exit contexts, send messages,
and manage the state of the system.
"""

from typing import Dict, List, Any, Optional

from phyelds.abstractions import Engine, NodeContext, EngineState


class MutableEngine(Engine):
    """
    MutableEngine is the responsible for managing the state and message passing
    in an aggregate computing system. It provides methods to enter and exit contexts,
    send messages, and manage the state of the system.
    """
    def __init__(self):
        super().__init__()
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
        if str(stack) in self.engine_state.state_trace:
            del self.engine_state.state_trace[str(stack)]

    def exit(self) -> None:
        if self.engine_state.stack:
            self.engine_state.stack.pop()
            self.engine_state.count_stack.pop()

    def current_path(self) -> list[str]:
        return self.engine_state.stack.copy()

    def write_state(self, value: Any, stack: List[str]) -> None:
        self.engine_state.state_trace[str(stack)] = value

    def read_state(self, stack: List[str]) -> Optional[Any]:
        self.engine_state.reads.add(str(stack))
        return self.engine_state.state_trace.get(str(stack))

    def send(self, data: Any) -> None:
        self.engine_state.to_send[str(self.engine_state.stack)] = data

    def aligned(self) -> List[int]:
        aligned: List[int] = []
        for node_id in self.engine_state.messages:
            if str(self.engine_state.stack) in self.engine_state.messages[node_id]:
                aligned.append(node_id)

        return aligned

    def aligned_values(self, path: List[str]) -> Dict[int, Any]:
        aligned: List[int] = self.aligned()
        path_str: str = str(path)
        aligned_values: Dict[int, Any] = {}
        # take the values of the given path
        for node_id in aligned:
            if path_str in self.engine_state.messages[node_id]:
                aligned_values[node_id] = self.engine_state.messages[node_id][path_str]
        return aligned_values

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

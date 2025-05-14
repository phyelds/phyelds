"""
Internal state class used to manage the state of the system (namely `rep` of field calculus).
"""

from typing import Any, Dict, Optional, List
import wrapt
from phyelds.abstractions import Engine


class Field:
    """
    Field class used to manage the interactions of between nodes (namely `nbr` of field calculus).
    It provides methods to perform operations on the field, such as addition,
    subtraction, multiplication, and division.
    You should never use it directly, but rather use the `neighbors` function
    """

    def __init__(self, data: Dict[int, Any], node_id: int) -> None:
        self.data = dict(sorted(data.items()))
        self._iter_index: Optional[int] = None
        self._iter_keys: Optional[List[int]] = None
        self.node_id = node_id

    def __iter__(self) -> "Field":
        self._iter_index = 0
        self._iter_keys = sorted(self.data.keys())
        return self

    def __next__(self) -> Any:
        if self._iter_keys is None or self._iter_index is None:
            raise StopIteration

        if self._iter_index >= len(self._iter_keys):
            self._iter_index = None
            self._iter_keys = None
            raise StopIteration

        key = self._iter_keys[self._iter_index]
        value = self.data[key]
        self._iter_index += 1
        return value

    def exclude_self(self) -> dict[int, Any]:
        """
        Exclude the current node from the field.
        :return:  A new Field object with the current node excluded.
        """
        to_return = self.data.copy()
        to_return.pop(self.node_id, None)
        return to_return

    def local(self):
        """
        Get the local value of the current node.
        :return:
        """
        return self.data.get(self.node_id, None)

    def select(self, field: "Field") -> list:
        """
        Select the values from the field that are present in the current field.
        :param field: The field to select from.
        :return:  A list of values from the current field that are present in the given field.
        """
        return [
            self.data[k] for k in self.data.keys() & field.data.keys() if field.data[k]
        ]

    def map(self, fn: callable) -> "Field":
        """
        Map a function to the field.
        :param fn: The function to map.
        :return: A new Field object with the mapped values.
        """
        return Field({k: fn(v) for k, v in self.data.items()}, self.node_id)

    # Helper method to apply binary operations
    def _apply_binary_op(self, other, op):
        if isinstance(other, Field):
            return Field(
                {
                    k: op(self.data[k], other.data[k])
                    for k in self.data.keys() & other.data.keys()
                },
                self.node_id,
            )
        return Field({k: op(v, other) for k, v in self.data.items()}, self.node_id)

    def __add__(self, other):
        return self._apply_binary_op(other, lambda a, b: a + b)

    def __sub__(self, other):
        return self._apply_binary_op(other, lambda a, b: a - b)

    def __mul__(self, other):
        return self._apply_binary_op(other, lambda a, b: a * b)

    def __truediv__(self, other):
        return self._apply_binary_op(other, lambda a, b: a / b)

    def __mod__(self, other):
        return self._apply_binary_op(other, lambda a, b: a % b)

    def __pow__(self, other):
        return self._apply_binary_op(other, lambda a, b: a**b)

    def __floordiv__(self, other):
        return self._apply_binary_op(other, lambda a, b: a // b)

    def __and__(self, other):
        return self._apply_binary_op(other, lambda a, b: a & b)

    def __or__(self, other):
        return self._apply_binary_op(other, lambda a, b: a | b)

    def __xor__(self, other):
        return self._apply_binary_op(other, lambda a, b: a ^ b)

    def __invert__(self):
        return Field({k: ~v for k, v in self.data.items()}, self.node_id)

    def __lt__(self, other):
        return self._apply_binary_op(other, lambda a, b: a < b)

    def __le__(self, other):
        return self._apply_binary_op(other, lambda a, b: a <= b)

    def __gt__(self, other):
        return self._apply_binary_op(other, lambda a, b: a > b)

    def __str__(self):
        """String representation of the field."""
        return self.__repr__()

    def __repr__(self):
        """String representation of the field."""
        return f"Field (id: {self.node_id}) -- data: {self.data} -- local: {self.local()}"


class State(wrapt.ObjectProxy):
    """
    A wrapper class that delegates operations to the underlying value
    while maintaining state management functionality.
    """

    def __init__(self, default: Any, path: List, engine: Engine):
        self.__wrapped__ = default  # then it will be updated
        state = engine.read_state(path)
        if state is None:
            value = default
            engine.write_state(default, path)
        else:
            value = state
        super().__init__(value)
        self._self_path = list(path)
        self._self_engine = engine

    @property
    def value(self) -> Any:
        """Get the current value."""
        return self.__wrapped__

    def update(self, new_value: Any) -> Any:
        """Update the stored value."""
        if isinstance(new_value, State):
            new_value = new_value.value
        self._self_engine.write_state(new_value, self._self_path)
        self.__wrapped__ = new_value
        return self

    def update_fn(self, fn: callable) -> Any:
        """Update the stored value using a function."""
        self.__wrapped__ = fn(self.__wrapped__)
        self._self_engine.write_state(self.__wrapped__, self._self_path)
        return self

    def forget(self):
        """Forget the stored value."""
        self._self_engine.forget(self._self_path)
        self.__wrapped__ = None

    def __str__(self):
        """String representation of the state."""
        return str(self.__wrapped__)

    def __repr__(self):
        """String representation of the state."""
        return f"State: {repr(self.__wrapped__)}"

    def __copy__(self):
        """Create a shallow copy of the state."""
        return State(self.__wrapped__, self._self_path, self._self_engine)

    def __deepcopy__(self, memo):
        """Create a deep copy of the state."""
        return self.__copy__()

    def __reduce__(self):
        """Reduce the state for pickling."""
        return self.__wrapped__

    def __reduce_ex__(self, protocol):
        """Reduce the state for pickling."""
        return self.__reduce__()

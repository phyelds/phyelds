"""
Internal state class used to manage the state of the system (namely `rep` of field calculus).
"""

from typing import Any, Dict, Optional, List
from fieldpy.abstractions import Engine
import wrapt

"""
Field class used to manage the interactions of between nodes (namely `nbr` of field calculus).
"""


class Field(object):
    def __init__(self, data: Dict[int, Any], engine: Engine) -> None:
        self.data = dict(sorted(data.items()))
        self._iter_index: Optional[int] = None
        self._iter_keys: Optional[List[int]] = None
        self.engine = engine

    def __iter__(self) -> "Field":
        self._iter_index = -1  # -1 represents the local value
        self._iter_keys = sorted(self.data.keys())
        return self

    def exclude_self(self):
        to_return = self.data.copy()
        to_return.pop(self.engine.id, None)
        return Field(to_return, self.engine)

    def local(self):
        return self.data.get(self.engine.id, None)

    def select(self, field) -> List:
        # take the element which are true from the field passed
        return [
            self.data[k] for k in self.data.keys() & field.data.keys() if field.data[k]
        ]

    # Helper method to apply binary operations
    def _apply_binary_op(self, other, op):
        if isinstance(other, Field):
            return Field(
                {
                    k: op(self.data[k], other.data[k])
                    for k in self.data.keys() & other.data.keys()
                },
                self.engine,
            )
        return Field({k: op(v, other) for k, v in self.data.items()}, self.engine)

    # Plus operator, namely it sums all the elements of the field
    def __add__(self, other):
        return self._apply_binary_op(other, lambda a, b: a + b)

    # Minus operator, namely it subtracts all the elements of the field
    def __sub__(self, other):
        return self._apply_binary_op(other, lambda a, b: a - b)

    # Multiplication operator, namely it multiplies all the elements of the field
    def __mul__(self, other):
        return self._apply_binary_op(other, lambda a, b: a * b)

    # Division operator, namely it divides all the elements of the field
    def __truediv__(self, other):
        return self._apply_binary_op(other, lambda a, b: a / b)

    # Modulo operator, namely it applies modulo to all the elements of the field
    def __mod__(self, other):
        return self._apply_binary_op(other, lambda a, b: a % b)

    # Power operator, namely it raises all the elements of the field to the power of the other
    def __pow__(self, other):
        return self._apply_binary_op(other, lambda a, b: a**b)

    # Floor division operator, namely it applies floor division to all the elements of the field
    def __floordiv__(self, other):
        return self._apply_binary_op(other, lambda a, b: a // b)

    # Bitwise and operator, namely it does a bitwise and operation on all the elements of the field
    def __and__(self, other):
        return self._apply_binary_op(other, lambda a, b: a & b)

    # Bitwise or operator, namely it does a bitwise or operation on all the elements of the field
    def __or__(self, other):
        return self._apply_binary_op(other, lambda a, b: a | b)

    # Bitwise xor operator, namely it does a bitwise xor operation on all the elements of the field
    def __xor__(self, other):
        return self._apply_binary_op(other, lambda a, b: a ^ b)

    # Bitwise not operator, namely it does a bitwise not operation on all the elements of the field
    def __invert__(self):
        return Field({k: ~v for k, v in self.data.items()}, self.engine)

    # Less than operator, namely it does a less than operation on all the elements of the field
    def __lt__(self, other):
        return self._apply_binary_op(other, lambda a, b: a < b)

    # Less than or equal operator, namely it does a less than or equal operation on all the elements of the field
    def __le__(self, other):
        return self._apply_binary_op(other, lambda a, b: a <= b)

    # Greater than operator, namely it does a greater than operation on all the elements of the field
    def __gt__(self, other):
        return self._apply_binary_op(other, lambda a, b: a > b)

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


class State(wrapt.ObjectProxy):
    """
    A wrapper class that delegates operations to the underlying value
    while maintaining state management functionality.
    """

    def __init__(self, default: Any, path: List, engine: Engine):
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

"""
Internal state class used to manage the state of the system (namely `rep` of field calculus).
"""

from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)
import wrapt
from phyelds.abstractions import Engine

# T represents the type of data held by the Field (e.g., int, float, bool)
T = TypeVar("T")
# U represents the type of data resulting from a map or operation
U = TypeVar("U")
# S represents the type of the value held by State
S = TypeVar("S")


class Field(Generic[T], Iterator[T]):
    """
    Field class used to manage the interactions of between nodes (namely `nbr` of field calculus).
    It provides methods to perform operations on the field, such as addition,
    subtraction, multiplication, and division.
    You should never use it directly, but rather use the `neighbors` function
    """

    def __init__(self, data: Dict[int, T], node_id: int) -> None:
        self.data: Dict[int, T] = dict(sorted(data.items()))
        self._iter_index: Optional[int] = None
        self._iter_keys: Optional[List[int]] = None
        self.node_id: int = node_id

    def __iter__(self) -> Iterator[T]:
        self._iter_index = 0
        self._iter_keys = sorted(self.data.keys())
        return self

    def __next__(self) -> T:
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

    def exclude_self(self) -> Dict[int, T]:
        """
        Exclude the current node from the field.
        :return:  A dictionary with the current node excluded.
        """
        to_return = self.data.copy()
        to_return.pop(self.node_id, None)
        return to_return

    def local(self) -> Optional[T]:
        """
        Get the local value of the current node.
        :return: The local value or None if not present.
        """
        return self.data.get(self.node_id, None)

    def select(self, field: "Field[Any]") -> List[T]:
        """
        Select the values from the field that are present in the current field.
        :param field: The field to select from (acts as a filter).
        :return:  A list of values from the current field that are present in the given field.
        """
        # We look at keys present in both, where the *other* field's value is truthy
        return [
            self.data[k] for k in self.data.keys() & field.data.keys() if field.data[k]
        ]

    def any(self) -> bool:
        """
        Check if any value in the field is truthy.
        :return: True if at least one value in the field is truthy, False otherwise.
        """
        return any(self.data.values())

    def all(self) -> bool:
        """
        Check if all values in the field are truthy.
        :return: True if all values in the field are truthy, False otherwise.
        """
        return all(self.data.values())

    def map(self, fn: Callable[[T], U]) -> "Field[U]":
        """
        Map a function to the field.
        :param fn: The function to map.
        :return: A new Field object with the mapped values.
        """
        return Field({k: fn(v) for k, v in self.data.items()}, self.node_id)

    # Helper method to apply binary operations
    def _apply_binary_op(
        self, other: Union["Field[Any]", Any], op: Callable[[Any, Any], Any]
    ) -> "Field[Any]":
        if isinstance(other, Field):
            return Field(
                {
                    k: op(self.data[k], other.data[k])
                    for k in self.data.keys() & other.data.keys()
                },
                self.node_id,
            )
        return Field({k: op(v, other) for k, v in self.data.items()}, self.node_id)

    def __add__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a + b)

    def __sub__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a - b)

    def __mul__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a / b)

    def __mod__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a % b)

    def __pow__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a**b)

    def __floordiv__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a // b)

    def __and__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a & b)

    def __or__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a | b)

    def __xor__(self, other: Any) -> "Field[Any]":
        return self._apply_binary_op(other, lambda a, b: a ^ b)

    def __invert__(self) -> "Field[Any]":
        return Field({k: ~v for k, v in self.data.items()}, self.node_id)  # type: ignore

    def __lt__(self, other: Any) -> "Field[bool]":
        return cast(Field[bool], self._apply_binary_op(other, lambda a, b: a < b))

    def __le__(self, other: Any) -> "Field[bool]":
        return cast(Field[bool], self._apply_binary_op(other, lambda a, b: a <= b))

    def __gt__(self, other: Any) -> "Field[bool]":
        return cast(Field[bool], self._apply_binary_op(other, lambda a, b: a > b))

    def __str__(self) -> str:
        """String representation of the field."""
        return self.__repr__()

    def __repr__(self) -> str:
        """String representation of the field."""
        return f"Field (id: {self.node_id}) -- data: {self.data} -- local: {self.local()}"


class State(wrapt.ObjectProxy, Generic[S]):
    """
    A wrapper class that delegates operations to the underlying value
    while maintaining state management functionality.
    """

    def __init__(self, default: S, path: List[Any], engine: Engine) -> None:
        self.__wrapped__: Optional[S]

        # Initialize internal storage before calling super init logic
        # (though wrapt handles __wrapped__ specifically)
        self.__wrapped__ = default

        state = engine.read_state(path)
        if state is None:
            value = default
            engine.write_state(default, path)
        else:
            value = state

        super().__init__(value)
        self._self_path: List[Any] = list(path)
        self._self_engine: Engine = engine

    @property
    def value(self) -> S:
        """Get the current value."""
        # wrapt proxies delegate attribute access, but explicit access to the wrapped object
        # is done via __wrapped__
        return cast(S, self.__wrapped__)

    @property
    def update_fn(self) -> Callable[[Union[S, "State[S]"]], "State[S]"]:
        """Get the update function."""
        return lambda value: self.___update(value)

    def ___update(self, new_value: Union[S, "State[S]"]) -> "State[S]":
        """Update the stored value."""
        val_to_store: S
        if isinstance(new_value, State):
            val_to_store = new_value.value
        else:
            val_to_store = new_value

        self._self_engine.write_state(val_to_store, self._self_path)
        self.__wrapped__ = val_to_store
        return self

    def forget(self) -> None:
        """Forget the stored value."""
        self._self_engine.forget(self._self_path)
        self.__wrapped__ = None

    def __str__(self) -> str:
        """String representation of the state."""
        return str(self.__wrapped__)

    def __repr__(self) -> str:
        """String representation of the state."""
        return f"State: {repr(self.__wrapped__)}"

    def __copy__(self) -> "State[S]":
        """Create a shallow copy of the state."""
        # Assuming S is the type of __wrapped__
        return State(cast(S, self.__wrapped__), self._self_path, self._self_engine)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "State[S]":
        """Create a deep copy of the state."""
        return self.__copy__()

    def __reduce__(self) -> Union[str, tuple]:
        """Reduce the state for pickling."""
        return self.__wrapped__  # type: ignore

    def __reduce_ex__(self, protocol: int) -> Union[str, tuple]:
        """Reduce the state for pickling."""
        return self.__reduce__()

"""
Internal classes used to manage the state and the neighborhood of the system
(namely `rep` and `nbr` of field calculus).
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

# T represents the type of data held by the Neighborhood (e.g., int, float, bool)
T = TypeVar("T")
# U represents the type of data resulting from a map or operation
U = TypeVar("U")
# S represents the type of the value held by State
S = TypeVar("S")
# StateT is the "mark" type for state values
StateT = Union[S, "State[S]"]  # pylint: disable=invalid-name


class NeighborhoodField(Generic[T], Iterator[T]):
    """
    NeighborhoodField class used to manage the interactions of between nodes
    (namely `nbr` of neighborhood calculus).
    It provides methods to perform operations on the neighborhood, such as addition,
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
        Exclude the current node from the neighborhood.
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

    def select(self, neighborhood: "NeighborhoodField[Any]") -> List[T]:
        """
        Select the values from the neighborhood that are present
        in the current neighborhood.
        :param neighborhood: The neighborhood to select from (acts as a filter).
        :return:  A list of values from the current neighborhood
                  that are present in the given neighborhood.
        """
        # We look at keys present in both, where the *other* neighborhood's value is truthy
        return [
            self.data[k]
            for k in self.data.keys() & neighborhood.data.keys()
            if neighborhood.data[k]
        ]

    def any(self) -> bool:
        """
        Check if any value in the neighborhood is truthy.
        :return: True if at least one value in the neighborhood is truthy, False otherwise.
        """
        return any(self.data.values())

    def all(self) -> bool:
        """
        Check if all values in the neighborhood are truthy.
        :return: True if all values in the neighborhood are truthy, False otherwise.
        """
        return all(self.data.values())

    def map(self, func: Callable[[T], U]) -> "NeighborhoodField[U]":
        """
        Map a function to the neighborhood.
        :param func: The function to map.
        :return: A new Neighborhood object with the mapped values.
        """
        return NeighborhoodField({k: func(v) for k, v in self.data.items()}, self.node_id)

    # Helper method to apply binary operations
    def _apply_binary_op(
        self, other: Union["NeighborhoodField[Any]", Any], op: Callable[[Any, Any], Any]
    ) -> "NeighborhoodField[Any]":
        if isinstance(other, NeighborhoodField):
            return NeighborhoodField(
                {
                    k: op(self.data[k], other.data[k])
                    for k in self.data.keys() & other.data.keys()
                },
                self.node_id,
            )
        return NeighborhoodField({k: op(v, other) for k, v in self.data.items()}, self.node_id)

    def __add__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a + b)

    def __sub__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a - b)

    def __mul__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a * b)

    def __truediv__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a / b)

    def __mod__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a % b)

    def __pow__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a**b)

    def __floordiv__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a // b)

    def __and__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a & b)

    def __or__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a | b)

    def __xor__(self, other: Any) -> "NeighborhoodField[Any]":
        return self._apply_binary_op(other, lambda a, b: a ^ b)

    def __invert__(self) -> "NeighborhoodField[Any]":
        return NeighborhoodField(
            {k: ~v for k, v in self.data.items()}, self.node_id
        )  # type: ignore

    def __lt__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a < b))

    def __le__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a <= b))

    def __gt__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a > b))

    def __str__(self) -> str:
        """String representation of the neighborhood."""
        return self.__repr__()

    def __repr__(self) -> str:
        """String representation of the neighborhood."""
        return f"Neighborhood (id: {self.node_id}) -- data: {self.data} -- local: {self.local()}"


class State(wrapt.ObjectProxy, Generic[S]):
    """
    A wrapper class that delegates operations to the underlying value
    while maintaining state management functionality.
    """

    def __init__(self, default: S, path: List[Any], engine: Engine) -> None:
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
        return self.__wrapped__

    @property
    def update_fn(self) -> Callable[["StateT[S]"], "StateT[S]"]:
        """Get the update function."""
        return lambda value: self.___update(value)  # pylint: disable=unnecessary-lambda

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

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
from phyelds.vm import Engine

# T represents the type of data held by the Neighborhood (e.g., int, float, bool)
T = TypeVar("T")
# U represents the type of data resulting from a map or operation
U = TypeVar("U")
# S represents the type of the value held by State
S = TypeVar("S")
# StateT is the "mark" type for state values
StateT = Union[S, "State[S]"]  # pylint: disable=invalid-name

_MISSING = object()


class NeighborhoodField(Generic[T], Iterator[T]):
    """
    NeighborhoodField class used to manage the interactions of between nodes
    (namely `nbr` of neighborhood calculus).
    It provides methods to perform operations on the neighborhood, such as addition,
    subtraction, multiplication, and division.
    You should never use it directly, but rather use the `neighbors` function
    """

    def __init__(self, data: Dict[int, T], node_id: int, default: Any = _MISSING) -> None:
        self.data: Dict[int, T] = dict(sorted(data.items()))
        self._iter_index: Optional[int] = None
        self._iter_keys: Optional[List[int]] = None
        self.node_id: int = node_id
        self.default: Optional[T] = (
            self.data.get(node_id, None) if default is _MISSING else cast(Optional[T], default)
        )

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

    def without_self(self) -> "NeighborhoodField[T]":
        """Return a new field containing only peer entries (excluding the local node)."""
        return NeighborhoodField(self.exclude_self(), self.node_id, default=self.default)

    def _values(self, include_self: bool) -> List[T]:
        if include_self:
            return list(self.data.values())
        return [value for node_id, value in self.data.items() if node_id != self.node_id]

    def _items(self, include_self: bool) -> List[tuple[int, T]]:
        if include_self:
            return list(self.data.items())
        return [(node_id, value) for node_id, value in self.data.items() if node_id != self.node_id]

    def local(self) -> Optional[T]:
        """
        Get the local value of the current node.
        :return: The local value or None if not present.
        """
        return self.data.get(self.node_id, None)

    def for_node(self, target_id: int) -> Optional[T]:
        """
        Return the value addressed to ``target_id``, falling back to ``default``.

        Args:
            target_id: The identifier of the recipient device.

        Returns:
            The value mapped to ``target_id`` if present, otherwise ``default``.
        """
        return self.data.get(target_id, self.default)

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

    def any(
        self,
        predicate: Optional[Callable[[T], bool]] = None,
        *,
        include_self: bool = True,
    ) -> bool:
        """
        Check if any value in the neighborhood satisfies ``predicate`` (or is truthy).

        Args:
            predicate: Optional condition to test each element against.
            include_self: Whether to include the local node's value.

        Returns:
            True if at least one value matches, False otherwise.
        """
        values = self._values(include_self)
        if predicate is None:
            return any(values)
        return any(predicate(value) for value in values)

    def all(
        self,
        predicate: Optional[Callable[[T], bool]] = None,
        *,
        include_self: bool = True,
    ) -> bool:
        """
        Check if all values in the neighborhood satisfy ``predicate`` (or are truthy).

        Args:
            predicate: Optional condition to test each element against.
            include_self: Whether to include the local node's value.

        Returns:
            True if every value matches, False otherwise.
        """
        values = self._values(include_self)
        if predicate is None:
            return all(values)
        return all(predicate(value) for value in values)

    def none(
        self,
        predicate: Optional[Callable[[T], bool]] = None,
        *,
        include_self: bool = True,
    ) -> bool:
        """
        Check that no value in the neighborhood satisfies ``predicate`` (or is truthy).

        Args:
            predicate: Optional condition to test each element against.
            include_self: Whether to include the local node's value.

        Returns:
            True if no value matches, False otherwise.
        """
        return not self.any(predicate, include_self=include_self)

    def count_matching(
        self,
        predicate: Callable[[T], bool],
        *,
        include_self: bool = True,
    ) -> int:
        """
        Count how many values in the neighborhood satisfy ``predicate``.

        Args:
            predicate: Condition to test each element against.
            include_self: Whether to include the local node's value.

        Returns:
            The number of matching elements.
        """
        return sum(1 for value in self._values(include_self) if predicate(value))

    def fold(
        self,
        initial: U,
        accumulator: Callable[[U, T], U],
        *,
        include_self: bool = True,
    ) -> U:
        """
        Fold the neighborhood values into a single result starting from ``initial``.

        Args:
            initial: Starting value for the accumulation.
            accumulator: Binary function ``(accumulated, element) -> accumulated``.
            include_self: Whether to include the local node's value.

        Returns:
            The accumulated result.
        """
        result = initial
        for value in self._values(include_self):
            result = accumulator(result, value)
        return result

    def reduce(
        self,
        reducer: Callable[[T, T], T],
        *,
        include_self: bool = True,
        default: Any = None,
    ) -> Any:
        """
        Reduce the neighborhood values with ``reducer``, returning ``default`` if empty.

        Args:
            reducer: Binary function combining two elements of type ``T``.
            include_self: Whether to include the local node's value.
            default: Fallback value returned when there are no elements to reduce.

        Returns:
            The reduced value, or ``default`` when empty.
        """
        values = self._values(include_self)
        if not values:
            return default
        result = values[0]
        for value in values[1:]:
            result = reducer(result, value)
        return result

    def min(
        self,
        *,
        include_self: bool = True,
        default: Any = None,
        key: Optional[Callable[[T], Any]] = None,
    ) -> Any:
        """
        Return the minimum value in the neighborhood, or ``default`` if empty.

        Args:
            include_self: Whether to include the local node's value.
            default: Fallback returned when no elements are present.
            key: Optional ordering key function.

        Returns:
            The minimal value, or ``default`` if empty.
        """
        values = self._values(include_self)
        if not values:
            return default
        if key is None:
            return min(values)  # type: ignore[type-var]
        return min(values, key=key)

    def max(
        self,
        *,
        include_self: bool = True,
        default: Any = None,
        key: Optional[Callable[[T], Any]] = None,
    ) -> Any:
        """
        Return the maximum value in the neighborhood, or ``default`` if empty.

        Args:
            include_self: Whether to include the local node's value.
            default: Fallback returned when no elements are present.
            key: Optional ordering key function.

        Returns:
            The maximal value, or ``default`` if empty.
        """
        values = self._values(include_self)
        if not values:
            return default
        if key is None:
            return max(values)  # type: ignore[type-var]
        return max(values, key=key)

    def sum(self, *, include_self: bool = True, start: Any = 0) -> Any:
        """Return the sum of the values in the neighborhood."""
        return self.fold(start, lambda acc, val: acc + val, include_self=include_self)

    def product(self, *, include_self: bool = True, start: Any = 1) -> Any:
        """Return the product of the values in the neighborhood."""
        return self.fold(start, lambda acc, val: acc * val, include_self=include_self)

    def id_of_min(
        self,
        *,
        include_self: bool = True,
        key: Optional[Callable[[int, T], Any]] = None,
    ) -> Optional[int]:
        """
        Return the node ID with the minimal value in the neighborhood, or ``None`` if empty.

        Args:
            include_self: Whether to include the local node.
            key: Optional function ``(node_id, value) -> comparable``.

        Returns:
            The ID of the winning entry, or ``None`` if empty.
        """
        items = self._items(include_self)
        if not items:
            return None
        selector: Callable[[tuple[int, T]], Any] = (
            (lambda item: item[1]) if key is None else (lambda item: key(item[0], item[1]))
        )
        return min(items, key=selector)[0]

    def id_of_max(
        self,
        *,
        include_self: bool = True,
        key: Optional[Callable[[int, T], Any]] = None,
    ) -> Optional[int]:
        """
        Return the node ID with the maximal value in the neighborhood, or ``None`` if empty.

        Args:
            include_self: Whether to include the local node.
            key: Optional function ``(node_id, value) -> comparable``.

        Returns:
            The ID of the winning entry, or ``None`` if empty.
        """
        items = self._items(include_self)
        if not items:
            return None
        selector: Callable[[tuple[int, T]], Any] = (
            (lambda item: item[1]) if key is None else (lambda item: key(item[0], item[1]))
        )
        return max(items, key=selector)[0]

    def coerce_in(self, lower: Any, upper: Any) -> "NeighborhoodField[T]":
        """
        Clamp every value in the field to the closed interval ``[lower, upper]``.

        Args:
            lower: Minimum allowed value.
            upper: Maximum allowed value.

        Returns:
            A new ``NeighborhoodField`` with clamped values.

        Raises:
            ValueError: If ``lower > upper``.
        """
        if lower > upper:
            raise ValueError(f"lower bound ({lower}) must not exceed upper bound ({upper})")
        return self.map(lambda value: min(upper, max(lower, value)))

    def replace_matching(
        self,
        replacement: T,
        predicate: Callable[[T], bool],
    ) -> "NeighborhoodField[T]":
        """
        Return a new field where values satisfying ``predicate`` are replaced with ``replacement``.

        Args:
            replacement: Value assigned to matching entries.
            predicate: Condition used to select values to replace.

        Returns:
            A new ``NeighborhoodField`` with matching values replaced.
        """
        return self.map(lambda value: replacement if predicate(value) else value)

    def map(self, func: Callable[[T], U]) -> "NeighborhoodField[U]":
        """
        Map a function to the neighborhood.
        :param func: The function to map.
        :return: A new Neighborhood object with the mapped values.
        """
        mapped_default = None if self.default is None else func(self.default)
        return NeighborhoodField(
            {k: func(v) for k, v in self.data.items()},
            self.node_id,
            default=mapped_default,
        )

    # Helper method to apply binary operations
    def _apply_binary_op(
        self, other: Union["NeighborhoodField[Any]", Any], op: Callable[[Any, Any], Any]
    ) -> "NeighborhoodField[Any]":
        if isinstance(other, NeighborhoodField):
            combined_default = (
                None
                if self.default is None or other.default is None
                else op(self.default, other.default)
            )
            return NeighborhoodField(
                {
                    k: op(self.data[k], other.data[k])
                    for k in self.data.keys() & other.data.keys()
                },
                self.node_id,
                default=combined_default,
            )
        scalar_default = None if self.default is None else op(self.default, other)
        return NeighborhoodField(
            {k: op(v, other) for k, v in self.data.items()},
            self.node_id,
            default=scalar_default,
        )

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
        inverted_default = None if self.default is None else ~self.default  # type: ignore
        return NeighborhoodField(
            {k: ~v for k, v in self.data.items()},
            self.node_id,
            default=inverted_default,
        )  # type: ignore

    def __lt__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a < b))

    def __le__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a <= b))

    def __gt__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a > b))

    def __ge__(self, other: Any) -> "NeighborhoodField[bool]":
        return cast(NeighborhoodField[bool], self._apply_binary_op(other, lambda a, b: a >= b))

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

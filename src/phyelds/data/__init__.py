"""
Internal classes used to manage the state and the neighborhood of the system
(namely `rep` and `nbr` of field calculus).
"""

import sys
from collections import OrderedDict
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

# T represents the type of data held by the Neighborhood (e.g., int, float, bool)
T = TypeVar("T")
# U represents the type of data resulting from a map or operation
U = TypeVar("U")

_MISSING = object()

# Fields go through devices by id: MicroPython dicts do not keep the sorted order.
_IS_MICROPYTHON = sys.implementation.name == "micropython"
_Sorted = OrderedDict if _IS_MICROPYTHON else dict


# A field is a collection with its own algebra: its many public methods are its API.
class NeighborhoodField(Generic[T], Iterator[T]):  # pylint: disable=too-many-public-methods
    """
    NeighborhoodField class used to manage the interactions between nodes
    (namely `nbr` of neighborhood calculus).
    It provides methods to perform operations on the neighborhood, such as addition,
    subtraction, multiplication, and division.
    You should never use it directly, but rather use the `neighbors` function
    """

    def __init__(
        self,
        data: Dict[int, T],
        node_id: int,
        default: Any = _MISSING,
        *,
        _sorted: bool = False,
    ) -> None:
        if not _IS_MICROPYTHON and (_sorted or len(data) <= 1):
            self.data: Dict[int, T] = data if _sorted else dict(data)
        else:
            self.data = _Sorted(sorted(data.items()))
        self._iter_index: Optional[int] = None
        self._iter_keys: Optional[List[int]] = None
        self.node_id: int = node_id
        self.default: Optional[T] = (
            self.data.get(node_id, None) if default is _MISSING else cast(Optional[T], default)
        )

    def __iter__(self) -> Iterator[T]:
        self._iter_index = 0
        self._iter_keys = sorted(self.data.keys()) if _IS_MICROPYTHON else list(self.data.keys())
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
        Return the values of the neighbors, without the current node.

        Returns:
            A new dictionary mapping each neighbor ID to its value; the field is unchanged.
        """
        to_return = self.data.copy()
        to_return.pop(self.node_id, None)
        return to_return

    def without_self(self) -> "NeighborhoodField[T]":
        """Return a new field containing only peer entries (excluding the local node)."""
        return NeighborhoodField(
            self.exclude_self(), self.node_id, default=self.default, _sorted=True
        )

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
        Return the value of the current node.

        Returns:
            The value of the current node, or ``None`` if the field has none.
        """
        return self.data.get(self.node_id, None)

    def with_local(self, value: T) -> "NeighborhoodField[T]":
        """
        Return a copy of the field where the current node has ``value``.

        The values of the neighbors and the default stay the same, and the field itself is
        not changed. If the field has no value for the current node, the copy adds it.

        Args:
            value: The new value of the current node.

        Returns:
            A new ``NeighborhoodField`` mapping the current node to ``value``.
        """
        updated = self.data.copy()
        replacing = self.node_id in updated  # a replaced value keeps the IDs in order
        updated[self.node_id] = value
        return NeighborhoodField(updated, self.node_id, default=self.default, _sorted=replacing)

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
        Return the values of the nodes for which ``neighborhood`` holds a truthy value.

        Args:
            neighborhood: The field used as a filter, typically a field of booleans.

        Returns:
            The values of this field, ordered by node ID, whose node is truthy in
                ``neighborhood``; nodes missing from ``neighborhood`` are left out.
        """
        # We look at keys present in both, where the *other* neighborhood's value is truthy
        return [self.data[k] for k in self.data if neighborhood.data.get(k, False)]

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

    def map(self, func: Callable[..., U], *values: Any) -> "NeighborhoodField[U]":
        """
        Apply ``func`` to every value of the field.

        Values of the device go to ``func`` through ``values``, after each entry, rather than
        through a closure: ``parents.map(operator.eq, local_id())`` rather than
        ``parents.map(lambda parent: parent == my_id)``. An engine running many devices at
        once then gives each entry the values of its own device.

        Args:
            func: The function to apply to each value (and to the default, if any).
            *values: Values of the device, passed to ``func`` after each value.

        Returns:
            A new ``NeighborhoodField`` with the mapped values.
        """
        mapped_default = None if self.default is None else func(self.default, *values)
        return NeighborhoodField(
            {k: func(v, *values) for k, v in self.data.items()},
            self.node_id,
            default=mapped_default,
            _sorted=True,
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
                {k: op(self.data[k], other.data[k]) for k in self.data if k in other.data},
                self.node_id,
                default=combined_default,
                _sorted=True,
            )
        scalar_default = None if self.default is None else op(self.default, other)
        return NeighborhoodField(
            {k: op(v, other) for k, v in self.data.items()},
            self.node_id,
            default=scalar_default,
            _sorted=True,
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
            _sorted=True,
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

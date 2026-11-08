"""
Unwrapping of the ``State``s an ``@aggregate`` function returns.

Kept out of ``phyelds.calculus`` so that MicroPython compiles the two modules apart, each
with a smaller peak of heap.
"""
from collections.abc import Sequence
from typing import Any

from phyelds.data import NeighborhoodField, State


def unwrap(value: Any) -> Any:
    """Replace the ``State``s in ``value`` with their values, copying only what holds one."""
    if isinstance(value, State):
        return value.value
    by_type = _BY_TYPE.get(type(value))
    if by_type is not None:
        return by_type(value)
    if isinstance(value, tuple):
        return _unwrap_tuple(value)
    if hasattr(value, "__dataclass_fields__") and not isinstance(value, type):
        return _unwrap_dataclass(value)
    return value


def _unwrap_tuple(value: tuple) -> tuple:
    """Unwrap the items of a tuple, keeping the type of a named tuple."""
    items = _unwrap_all(value)
    if items is value:
        return value
    if type(value) is tuple:  # pylint: disable=unidiomatic-typecheck
        return tuple(items)
    # A named tuple; MicroPython's ones have no ``_fields`` to tell them apart.
    return type(value)(*items)


def _unwrap_dict(value: dict) -> dict:
    """Unwrap the keys and the values of a dict."""
    keys, items = list(value), list(value.values())
    unwrapped_keys, unwrapped_items = _unwrap_all(keys), _unwrap_all(items)
    if unwrapped_keys is keys and unwrapped_items is items:
        return value
    return dict(zip(unwrapped_keys, unwrapped_items))


def _unwrap_dataclass(value: Any) -> Any:
    """Unwrap the fields of a dataclass, building a new one with its constructor."""
    # The MicroPython stand-in lists the field names in a tuple, CPython keys a dict by them.
    names = list(value.__dataclass_fields__)
    items = [getattr(value, name) for name in names]
    unwrapped = _unwrap_all(items)
    if unwrapped is items:
        return value
    return type(value)(**dict(zip(names, unwrapped)))


def _unwrap_set(value: set | frozenset) -> set | frozenset:
    """Unwrap the items of a set or a frozenset."""
    items = list(value)
    unwrapped = _unwrap_all(items)
    return value if unwrapped is items else type(value)(unwrapped)


def _unwrap_field(value: NeighborhoodField) -> NeighborhoodField:
    """Unwrap the values of a field and its default."""
    data, default = _unwrap_dict(value.data), unwrap(value.default)
    if data is value.data and default is value.default:
        return value
    return NeighborhoodField(data, value.node_id, default=default)


def _unwrap_all(values: Sequence[Any]) -> Any:
    """Unwrap each of ``values``: ``values`` itself if none changes, else a list of them."""
    unwrapped = [unwrap(item) for item in values]
    if all(new is old for new, old in zip(unwrapped, values)):
        return values
    return unwrapped


# The containers unwrapped by their exact type; subclasses may not rebuild the same way.
_BY_TYPE = {
    list: _unwrap_all,
    dict: _unwrap_dict,
    set: _unwrap_set,
    frozenset: _unwrap_set,
    NeighborhoodField: _unwrap_field,
}

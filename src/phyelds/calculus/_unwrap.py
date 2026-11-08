"""
Unwrapping of the ``State``s an ``@aggregate`` function returns.

Kept out of ``phyelds.calculus`` so that MicroPython compiles the two modules apart, each
with a smaller peak of heap.
"""
from collections.abc import Sequence
from typing import Any

from phyelds.data import State


def unwrap(value: Any) -> Any:
    """Replace the ``State``s in ``value`` with their values, copying only what holds one."""
    if isinstance(value, State):
        return value.value
    if type(value) is list:  # pylint: disable=unidiomatic-typecheck
        return _unwrap_all(value)
    if isinstance(value, tuple):
        return _unwrap_tuple(value)
    if type(value) is dict:  # pylint: disable=unidiomatic-typecheck
        return _unwrap_dict(value)
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


def _unwrap_all(values: Sequence[Any]) -> Any:
    """Unwrap each of ``values``: ``values`` itself if none changes, else a list of them."""
    unwrapped = [unwrap(item) for item in values]
    if all(new is old for new, old in zip(unwrapped, values)):
        return values
    return unwrapped

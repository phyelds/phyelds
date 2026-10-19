"""
Wire format of the messages of a device: the outbox of ``Engine.cooldown`` to bytes and back.

The bytes are JSON, available on CPython and MicroPython alike, so that devices on either
runtime understand each other. What JSON cannot say (tuples, sets, keys that are not
strings, infinities, fields, the dataclasses of the libraries) is written as an object
with a single tag key; plain JSON objects never appear, so the tags cannot clash.
"""
import json
from collections.abc import Mapping
from typing import Any

from phyelds.data import NeighborhoodField, State

_BY_NAME: dict[str, Any] = {}
_CLASS_NAMES: dict[type, str] = {}
_CONSTANT_NAMES: dict[int, str] = {}
_NON_FINITE = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}


def register(kind: Any, name: str | None = None) -> Any:
    """
    Let a dataclass, or a constant such as a sentinel, travel in messages.

    A dataclass travels as its fields; a constant is restored as the very same object,
    so that it can still be compared with ``is``.

    Args:
        kind: A dataclass, or any other object to treat as a constant.
        name: Name on the wire, the same on every device. Defaults to the class name.

    Returns:
        ``kind``, so that ``register`` can be used as a class decorator.

    Raises:
        ValueError: If ``kind`` is a constant and ``name`` is missing.
    """
    if isinstance(kind, type):
        _CLASS_NAMES[kind] = name or kind.__name__
        _BY_NAME[_CLASS_NAMES[kind]] = kind
        return kind
    if name is None:
        raise ValueError("a constant needs a name to be registered")
    _CONSTANT_NAMES[id(kind)] = name
    _BY_NAME[name] = kind
    return kind


def encode(outbox: Mapping[Any, Any]) -> bytes:
    """
    Encode the messages a device sends.

    Args:
        outbox: The messages, as returned by ``Engine.cooldown``.

    Returns:
        The UTF-8 JSON bytes to send.

    Raises:
        TypeError: If a value is of a type the codec does not know; see ``register``.
    """
    return json.dumps(_to_json(outbox)).encode()


def decode(payload: bytes) -> dict[Any, Any]:
    """
    Decode the messages received from a device.

    Args:
        payload: Bytes produced by ``encode``.

    Returns:
        The messages, ready to be given to ``Engine.setup``.
    """
    return _from_json(json.loads(payload))


def _to_json(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    """Rewrite ``value`` with JSON types only."""
    if isinstance(value, State):
        value = value.value
    if id(value) in _CONSTANT_NAMES:
        return {"c": _CONSTANT_NAMES[id(value)]}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value - value == 0 else {"f": repr(value)}
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, tuple):
        return {"t": [_to_json(item) for item in value]}
    if isinstance(value, (set, frozenset)):
        return {"s": [_to_json(item) for item in value]}
    if isinstance(value, dict):
        return {"d": [[_to_json(key), _to_json(item)] for key, item in value.items()]}
    if isinstance(value, NeighborhoodField):
        return {"n": [value.node_id, _to_json(value.data), _to_json(value.default)]}
    if type(value) in _CLASS_NAMES:
        fields = [_to_json(getattr(value, field)) for field in value.__dataclass_fields__]
        return {"o": [_CLASS_NAMES[type(value)], fields]}
    raise TypeError(f"cannot encode {type(value).__name__}: register it in phyelds.data.codec")


def _from_json(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    """Undo ``_to_json``."""
    if isinstance(value, list):
        return [_from_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    (tag, content), = value.items()
    if tag == "c":
        return _BY_NAME[content]
    if tag == "f":
        return _NON_FINITE[content]
    if tag == "o":
        name, fields = content
        return _BY_NAME[name](*_from_json(fields))
    items = _from_json(content)
    if tag == "t":
        return tuple(items)
    if tag == "s":
        return set(items)
    if tag == "d":
        return dict(items)
    node_id, data, default = items
    return NeighborhoodField(data, node_id, default=default)

"""
Wire format of the messages of a device: the outbox of ``Engine.cooldown`` to bytes and back.

Two formats, which work alike on CPython and MicroPython, so that devices on either runtime
understand each other. JSON, the default, is readable: what JSON cannot say (tuples, sets,
keys that are not strings, infinities, fields, the dataclasses of the libraries) is written
as an object with a single tag key; plain JSON objects never appear, so the tags cannot
clash. The binary format is smaller, above all with compact paths: a tag byte before each
value instead of the syntax of JSON. ``decode`` tells them apart by the first byte, so
devices sending either can share a network.
"""
import json
from collections.abc import Mapping
from typing import Any

from phyelds.data import NeighborhoodField, State
from phyelds.data._registry import BY_NAME, CLASS_NAMES, CONSTANT_NAMES

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
        CLASS_NAMES[kind] = name or kind.__name__
        BY_NAME[CLASS_NAMES[kind]] = kind
        return kind
    if name is None:
        raise ValueError("a constant needs a name to be registered")
    CONSTANT_NAMES[id(kind)] = name
    BY_NAME[name] = kind
    return kind


def encode(outbox: Mapping[Any, Any], binary: bool = False) -> bytes:
    """
    Encode the messages a device sends.

    Args:
        outbox: The messages, as returned by ``Engine.cooldown``.
        binary: Whether to write the binary format, smaller, instead of JSON.

    Returns:
        The bytes to send.

    Raises:
        TypeError: If a value is of a type the codec does not know; see ``register``.
    """
    if binary:
        # Imported when used: a device that only sends and receives JSON keeps its memory.
        from phyelds.data import _binary  # pylint: disable=import-outside-toplevel
        return _binary.encode(outbox)
    return json.dumps(_to_json(outbox)).encode()


def decode(payload: bytes) -> dict[Any, Any]:
    """
    Decode the messages received from a device, in either format.

    Args:
        payload: Bytes produced by ``encode``.

    Returns:
        The messages, ready to be given to ``Engine.setup``.

    Raises:
        ValueError: If the first byte of ``payload`` is not that of a format of the codec.
    """
    if payload[:1] == b"{":
        return _from_json(json.loads(payload))
    from phyelds.data import _binary  # pylint: disable=import-outside-toplevel
    return _binary.decode(payload)


def _to_json(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    """Rewrite ``value`` with JSON types only."""
    if isinstance(value, State):
        value = value.value
    if id(value) in CONSTANT_NAMES:
        return {"c": CONSTANT_NAMES[id(value)]}
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
    if type(value) in CLASS_NAMES:
        fields = [_to_json(getattr(value, field)) for field in value.__dataclass_fields__]
        return {"o": [CLASS_NAMES[type(value)], fields]}
    raise TypeError(f"cannot encode {type(value).__name__}: register it in phyelds.data.codec")


def _from_json(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    """Undo ``_to_json``."""
    if isinstance(value, list):
        return [_from_json(item) for item in value]
    if not isinstance(value, dict):
        return value
    (tag, content), = value.items()
    if tag == "c":
        return BY_NAME[content]
    if tag == "f":
        return _NON_FINITE[content]
    if tag == "o":
        name, fields = content
        return BY_NAME[name](*_from_json(fields))
    items = _from_json(content)
    if tag == "t":
        return tuple(items)
    if tag == "s":
        return set(items)
    if tag == "d":
        return dict(items)
    node_id, data, default = items
    return NeighborhoodField(data, node_id, default=default)

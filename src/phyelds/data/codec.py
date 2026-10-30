"""
Wire format of the messages of a device: the outbox of ``Engine.cooldown`` to bytes and back.

The bytes are JSON, available on CPython and MicroPython alike, so that devices on either
runtime understand each other. What JSON cannot say (tuples, sets, keys that are not
strings, infinities, fields, the dataclasses of the libraries) is written as an object
with a single tag key; plain JSON objects never appear, so the tags cannot clash.
"""
import json
import struct
from collections.abc import Mapping
from typing import Any

from phyelds.data import NeighborhoodField, State

_BY_NAME: dict[str, Any] = {}
_CLASS_NAMES: dict[type, str] = {}
_CONSTANT_NAMES: dict[int, str] = {}
_NON_FINITE = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}
# The first byte of a payload: JSON objects start with "{". In the binary format, the keys of
# the messages are values like the others, or, when they all are, 32-bit unsigned integers.
_JSON = 0x7B
_BINARY = 0x01
_BINARY_UINT32_KEYS = 0x02
# The first byte of each value in the binary format.
(_NONE, _FALSE, _TRUE, _INT, _F32, _F64, _STR,
 _LIST, _TUPLE, _SET, _DICT, _FIELD, _OBJECT, _CONSTANT) = range(14)
_SEQUENCES = {_LIST: list, _TUPLE: tuple, _SET: set}


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
    if not binary:
        return json.dumps(_to_json(outbox)).encode()
    uint32_keys = all(isinstance(key, int) and 0 <= key <= 0xFFFFFFFF for key in outbox)
    out = bytearray([_BINARY_UINT32_KEYS if uint32_keys else _BINARY])
    for key, item in outbox.items():
        if uint32_keys:
            out.extend(struct.pack("<I", key))
        else:
            _write(key, out)
        _write(item, out)
    return bytes(out)


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
    kind = payload[0] if payload else None
    if kind == _JSON:
        return _from_json(json.loads(payload))
    if kind not in (_BINARY, _BINARY_UINT32_KEYS):
        raise ValueError(f"unknown format {payload[:1]!r}: not a payload of phyelds.data.codec")
    messages = {}
    at = 1
    while at < len(payload):
        if kind == _BINARY_UINT32_KEYS:
            key, at = struct.unpack_from("<I", payload, at)[0], at + 4
        else:
            key, at = _read(payload, at)
        messages[key], at = _read(payload, at)
    return messages


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


def _write(value: Any, out: bytearray) -> None:  # pylint: disable=too-many-branches
    """Append ``value`` to ``out`` in the binary format, as ``_to_json`` does in JSON."""
    if isinstance(value, State):
        value = value.value
    if id(value) in _CONSTANT_NAMES:
        out.append(_CONSTANT)
        _write_text(_CONSTANT_NAMES[id(value)], out)
    elif value is None or isinstance(value, bool):
        out.append(_NONE if value is None else _TRUE if value else _FALSE)
    elif isinstance(value, int):
        out.append(_INT)
        _write_unsigned(value << 1 if value >= 0 else -2 * value - 1, out)  # zigzag
    elif isinstance(value, float):
        _write_float(value, out)
    elif isinstance(value, str):
        out.append(_STR)
        _write_text(value, out)
    elif isinstance(value, (list, tuple, set, frozenset)):
        tag = _LIST if isinstance(value, list) else _TUPLE if isinstance(value, tuple) else _SET
        out.append(tag)
        _write_items(value, out)
    elif isinstance(value, dict):
        out.append(_DICT)
        _write_pairs(value, out)
    elif isinstance(value, NeighborhoodField):
        out.append(_FIELD)
        _write(value.node_id, out)
        _write_pairs(value.data, out)
        _write(value.default, out)
    elif type(value) in _CLASS_NAMES:
        out.append(_OBJECT)
        _write_text(_CLASS_NAMES[type(value)], out)
        _write_items([getattr(value, field) for field in value.__dataclass_fields__], out)
    else:
        raise TypeError(f"cannot encode {type(value).__name__}: register it in phyelds.data.codec")


def _write_unsigned(number: int, out: bytearray) -> None:
    """Append ``number`` as a varint: 7 bits per byte, the high bit set on all but the last."""
    while number > 0x7F:
        out.append(number & 0x7F | 0x80)
        number >>= 7
    out.append(number)


def _write_items(items: Any, out: bytearray) -> None:
    _write_unsigned(len(items), out)
    for item in items:
        _write(item, out)


def _write_pairs(mapping: Mapping[Any, Any], out: bytearray) -> None:
    _write_unsigned(len(mapping), out)
    for key, item in mapping.items():
        _write(key, out)
        _write(item, out)


def _write_float(number: float, out: bytearray) -> None:
    """Append ``number`` in 32 bits if they hold it exactly, in 64 otherwise."""
    try:
        single = struct.pack("<f", number)
    except OverflowError:  # CPython, beyond 32 bits; MicroPython gives an infinity instead
        single = b""
    if single and struct.unpack("<f", single)[0] == number:
        out.append(_F32)
        out.extend(single)
    else:
        out.append(_F64)
        out.extend(struct.pack("<d", number))


def _write_text(text: str, out: bytearray) -> None:
    data = text.encode()
    _write_unsigned(len(data), out)
    out.extend(data)


def _read(payload: bytes, at: int) -> tuple[Any, int]:  # pylint: disable=too-many-return-statements
    """Undo ``_write``: the value at ``at``, and where the next one starts."""
    tag = payload[at]
    at += 1
    if tag <= _TRUE:
        return (None, False, True)[tag], at
    if tag == _INT:
        number, at = _read_unsigned(payload, at)
        return number >> 1 ^ -(number & 1), at
    if tag == _F32:
        return struct.unpack_from("<f", payload, at)[0], at + 4
    if tag == _F64:
        return struct.unpack_from("<d", payload, at)[0], at + 8
    if tag == _STR:
        return _read_text(payload, at)
    if tag in _SEQUENCES:
        items, at = _read_items(payload, at)
        return _SEQUENCES[tag](items), at
    if tag == _DICT:
        return _read_pairs(payload, at)
    if tag == _FIELD:
        node_id, at = _read(payload, at)
        data, at = _read_pairs(payload, at)
        default, at = _read(payload, at)
        return NeighborhoodField(data, node_id, default=default), at
    name, at = _read_text(payload, at)
    if tag == _CONSTANT:
        return _BY_NAME[name], at
    fields, at = _read_items(payload, at)
    return _BY_NAME[name](*fields), at


def _read_items(payload: bytes, at: int) -> tuple[list, int]:
    count, at = _read_unsigned(payload, at)
    items = []
    for _ in range(count):
        item, at = _read(payload, at)
        items.append(item)
    return items, at


def _read_pairs(payload: bytes, at: int) -> tuple[dict, int]:
    count, at = _read_unsigned(payload, at)
    pairs = {}
    for _ in range(count):
        key, at = _read(payload, at)
        pairs[key], at = _read(payload, at)
    return pairs, at


def _read_unsigned(payload: bytes, at: int) -> tuple[int, int]:
    number = shift = 0
    while payload[at] > 0x7F:
        number |= (payload[at] & 0x7F) << shift
        shift += 7
        at += 1
    return number | payload[at] << shift, at + 1


def _read_text(payload: bytes, at: int) -> tuple[str, int]:
    length, at = _read_unsigned(payload, at)
    return payload[at:at + length].decode(), at + length

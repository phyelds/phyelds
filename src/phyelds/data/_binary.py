"""
The binary format of ``phyelds.data.codec``, which the MicroPython page of the docs
describes for other runtimes: what ``_to_json`` writes as JSON, with a tag byte before each
value instead of the syntax of JSON.
"""
import struct
from collections.abc import Mapping
from typing import Any

from phyelds.data import NeighborhoodField, State
from phyelds.data._registry import BY_NAME, CLASS_NAMES, CONSTANT_NAMES

_BINARY = 0x01
_BINARY_UINT32_KEYS = 0x02
(_NONE, _FALSE, _TRUE, _INT, _F32, _F64, _STR,
 _LIST, _TUPLE, _SET, _DICT, _FIELD, _OBJECT, _CONSTANT) = range(14)
_SEQUENCES = {_LIST: list, _TUPLE: tuple, _SET: set}


def encode(outbox: Mapping[Any, Any]) -> bytes:
    """The binary payload of ``outbox``; see ``phyelds.data.codec.encode``."""
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
    """The messages of a binary payload; see ``phyelds.data.codec.decode``."""
    kind = payload[0] if payload else None
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


def _write(value: Any, out: bytearray) -> None:  # pylint: disable=too-many-branches
    """Append ``value`` to ``out`` in the binary format, as ``_to_json`` does in JSON."""
    if isinstance(value, State):
        value = value.value
    if id(value) in CONSTANT_NAMES:
        out.append(_CONSTANT)
        _write_text(CONSTANT_NAMES[id(value)], out)
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
    elif type(value) in CLASS_NAMES:
        out.append(_OBJECT)
        _write_text(CLASS_NAMES[type(value)], out)
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
        return BY_NAME[name], at
    fields, at = _read_items(payload, at)
    return BY_NAME[name](*fields), at


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

"""The bytes a node sends on the shared topic: its id, a header and the payload of its device."""
import json
from collections.abc import Mapping
from typing import Any


def pack(sender: Any, header: Mapping[str, Any], payload: bytes) -> bytes:
    """
    The message of ``sender``, with ``header`` before the ``payload`` of its device.

    Args:
        sender: The id of the device that sends, serialisable as JSON.
        header: What the neighbourhood strategy of the receivers needs, serialisable as JSON.
        payload: The bytes of the round of the device.

    Returns:
        One line of JSON, then the payload as it is.
    """
    return json.dumps([sender, dict(header)]).encode() + b"\n" + payload


def unpack(data: bytes) -> tuple[Any, dict[str, Any], bytes]:
    """
    The sender, the header and the payload of a message that ``pack`` built.

    Args:
        data: The bytes received.

    Returns:
        The sender, its header and the payload of its device.
    """
    line, _, payload = data.partition(b"\n")
    sender, header = json.loads(line)
    return sender, header, payload

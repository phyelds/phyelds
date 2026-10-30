"""
A device that exchanges its messages as bytes: the building block of hosts where each device
runs on its own (a microcontroller, a robot controller) and talks over a radio.
"""
from collections.abc import Callable, Mapping
from typing import Any

from phyelds import engine
from phyelds.data import NeighborhoodField, State
from phyelds.data.codec import decode, encode
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine


class Device:  # pylint: disable=too-many-instance-attributes
    """
    The rounds of one device, with its messages as bytes: sending and receiving them is up
    to the host.

    Args:
        device_id: The id of the device, unique in the network.
        program: The ``@aggregate`` function to run in each round.
        paths: How the engine encodes alignment paths: ``"debug"``, ``"compact"``, or an
            encoding of one's own (see ``MutableEngine``); devices that talk to each other
            must use the same.
        binary: Whether to send the binary format of ``phyelds.data.codec``, smaller, instead
            of JSON. Devices understand both, whichever they send.
        messages: What the device sends: ``"shared"``, the same message to every neighbor,
            with whole fields; or ``"addressed"``, besides the message for every neighbor,
            one addressed to each neighbor heard from, with its value of each field instead
            of the whole field (see ``addressed``), so that the messages do not grow with
            the neighbors. The devices that receive addressed messages must know them too:
            an older version takes a message addressed to another device for its own.
        lifetime: For how many rounds a message is used if its sender does not send a newer
            one. ``1`` keeps only the messages received since the last round.

    Raises:
        ValueError: If ``messages`` is neither ``"shared"`` nor ``"addressed"``.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        device_id: Any,
        program: Callable[[], Any],
        *,
        paths: Any = "debug",
        binary: bool = False,
        messages: str = "shared",
        lifetime: int = 1,
    ):
        if messages not in ("shared", "addressed"):
            raise ValueError(f"messages must be 'shared' or 'addressed', not {messages!r}")
        self.device_id = device_id
        self.program = program
        self.paths = paths
        self.binary = binary
        self.messages = messages
        self.lifetime = lifetime
        self.result: Any = None
        """The value the program computed in the last round."""
        self.outputs: dict[str, Any] = {}
        """What the program stored with ``store`` in the last round."""
        self.addressed: dict[Any, bytes] = {}
        """
        With ``"addressed"`` messages, the bytes to send to each neighbor heard from, after
        the last round: empty when the program sends no field, as the bytes for every
        neighbor then serve them all.
        """
        self._state: dict[Any, Any] = {}
        # sender -> [messages, rounds since they were received, whether addressed to this device]
        self._inbox: dict[Any, list] = {}
        # No value is sent at the empty path: its key carries the recipient of a message.
        self._recipient_key = MutableEngine(paths=paths).key([])

    def receive(self, sender: Any, payload: bytes) -> None:
        """
        Keep the last message of ``sender`` for the next rounds.

        A message addressed to another device is left out, and so is a message for every
        neighbor while one addressed to this device, received since its last round, is
        kept: send the addressed messages first.

        Args:
            sender: The id of the device that sent ``payload``.
            payload: The bytes it sent: those ``run_round`` returns, or one of ``addressed``.

        Raises:
            ValueError: If ``payload`` is not a payload of ``phyelds.data.codec``.
        """
        messages = decode(payload)
        recipient = messages.pop(self._recipient_key, None)
        if recipient is not None and recipient != self.device_id:
            return
        held = self._inbox.get(sender)
        if recipient is None and held is not None and held[2] and held[1] == 0:
            return
        self._inbox[sender] = [messages, 0, recipient is not None]

    def run_round(self, sensors: Mapping[str, Any]) -> bytes:
        """
        Run the program once.

        Args:
            sensors: The sensors of the device in this round, by name.

        Returns:
            The bytes to send to every neighbor; with ``"addressed"`` messages, also send
            those of ``addressed``, first.
        """
        for sender in list(self._inbox):
            self._inbox[sender][1] += 1
            if self._inbox[sender][1] > self.lifetime:
                del self._inbox[sender]
        received = {sender: entry[0] for sender, entry in self._inbox.items()}
        engine.set(MutableEngine(paths=self.paths))
        context = NodeContext(self.device_id, dict(sensors))
        engine.get().setup(context, received, self._state)
        result = self.program()
        outbox = engine.get().cooldown()  # first: it also drops the state not used
        self._state = engine.get().state_trace()
        self.outputs = context.outputs
        self.result = result.value if isinstance(result, State) else result
        self.addressed = {}
        fields = any(isinstance(value, NeighborhoodField) for value in outbox.values())
        if self.messages == "addressed" and fields:
            for neighbor in received:
                message = _for(outbox, neighbor)
                message[self._recipient_key] = neighbor
                self.addressed[neighbor] = encode(message, self.binary)
            outbox = _for(outbox, None)
        return encode(outbox, self.binary)


def _for(outbox: Mapping[Any, Any], neighbor: Any) -> dict[Any, Any]:
    """``outbox``, each field reduced to its value for ``neighbor`` (its default for ``None``)."""
    return {
        key: value.for_node(neighbor) if isinstance(value, NeighborhoodField) else value
        for key, value in outbox.items()
    }

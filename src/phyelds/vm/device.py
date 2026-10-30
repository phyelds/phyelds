"""
A device that exchanges its messages as bytes: the building block of hosts where each device
runs on its own (a microcontroller, a robot controller) and talks over a radio.
"""
from collections.abc import Callable, Mapping
from typing import Any

from phyelds import engine
from phyelds.data import State
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
        lifetime: For how many rounds a message is used if its sender does not send a newer
            one. ``1`` keeps only the messages received since the last round.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        device_id: Any,
        program: Callable[[], Any],
        *,
        paths: Any = "debug",
        binary: bool = False,
        lifetime: int = 1,
    ):
        self.device_id = device_id
        self.program = program
        self.paths = paths
        self.binary = binary
        self.lifetime = lifetime
        self.result: Any = None
        """The value the program computed in the last round."""
        self.outputs: dict[str, Any] = {}
        """What the program stored with ``store`` in the last round."""
        self._state: dict[Any, Any] = {}
        self._inbox: dict[Any, list] = {}  # sender -> [payload, rounds since it was received]

    def receive(self, sender: Any, payload: bytes) -> None:
        """
        Keep the last message of ``sender`` for the next rounds.

        Args:
            sender: The id of the device that sent ``payload``.
            payload: The bytes it sent, as returned by its ``run_round``.
        """
        self._inbox[sender] = [payload, 0]

    def run_round(self, sensors: Mapping[str, Any]) -> bytes:
        """
        Run the program once.

        Args:
            sensors: The sensors of the device in this round, by name.

        Returns:
            The bytes to send to the neighbors.
        """
        for sender in list(self._inbox):
            self._inbox[sender][1] += 1
            if self._inbox[sender][1] > self.lifetime:
                del self._inbox[sender]
        messages = {sender: decode(payload) for sender, (payload, _) in self._inbox.items()}
        engine.set(MutableEngine(paths=self.paths))
        context = NodeContext(self.device_id, dict(sensors))
        engine.get().setup(context, messages, self._state)
        result = self.program()
        outbox = engine.get().cooldown()  # first: it also drops the state not used
        self._state = engine.get().state_trace()
        self.outputs = context.outputs
        self.result = result.value if isinstance(result, State) else result
        return encode(outbox, self.binary)

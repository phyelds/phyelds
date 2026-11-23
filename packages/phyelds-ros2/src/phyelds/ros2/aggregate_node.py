"""The rounds of an aggregate program on a ROS 2 node, apart from ROS: what it hears and sends."""
from collections.abc import Callable, Mapping
from typing import Any

from phyelds.ros2.message import pack, unpack
from phyelds.ros2.neighbourhood import Neighbour, Neighbourhood, Reachable
from phyelds.vm.device import Device


class AggregateNode:  # pylint: disable=too-many-instance-attributes
    """
    Runs an aggregate program on one robot, from the messages its node hears on a shared topic.

    The host gives it what the robot hears (``hear``) and what it senses on its topics
    (``sense``), runs a round at each tick of its timer (``run_round``), publishes the bytes
    it returns, and acts on the ``outputs``. The ``position`` sensor, in a frame all the nodes
    share, is the one the neighbourhood measures from.

    Args:
        device_id: The id of the robot, unique among the nodes that share the topic.
        program: The ``@aggregate`` function to run.
        neighbourhood: Which senders are neighbours; ``Reachable()`` by default.
        sensors: Extra sensors, read at each round, over those sensed on the topics.
        paths: The path mode of the engine: the same on every node.
        lifetime: For how many rounds the message of a silent neighbour is kept. Timers of
            different nodes drift apart, so a neighbour may send twice or not at all between
            two rounds: ``2`` keeps it through one round without a message.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        device_id: str,
        program: Callable[[], Any],
        *,
        neighbourhood: Neighbourhood | None = None,
        sensors: Callable[[], Mapping[str, Any]] | None = None,
        paths: str = "compact",
        lifetime: int = 2,
    ):
        self.device_id = device_id
        self.neighbourhood = Reachable() if neighbourhood is None else neighbourhood
        self.sensors = sensors
        self.lifetime = lifetime
        self.readings: dict[str, Any] = {}
        """The latest value of each sensor sensed on the topics."""
        self._device = Device(device_id, program, paths=paths, lifetime=lifetime)
        # sender -> [what the neighbourhood measured of it, rounds since it was heard]
        self._measured: dict[Any, list] = {}

    @property
    def result(self) -> Any:
        """The value the program computed in the last round."""
        return self._device.result

    @property
    def outputs(self) -> dict[str, Any]:
        """What the program stored with ``store`` in the last round."""
        return self._device.outputs

    @property
    def position(self) -> Any:
        """The ``position`` sensed on the topics; ``None`` until sensed."""
        return self.readings.get("position")

    def sense(self, readings: Mapping[str, Any]) -> None:
        """
        Take sensors sensed on a topic: they hold until sensed again.

        Args:
            readings: The sensors, by name.
        """
        self.readings.update(readings)

    def hear(self, data: bytes) -> None:
        """
        Take a message heard on the shared topic, for the next round, if its sender is a neighbour.

        Args:
            data: The bytes a node published, possibly this one.
        """
        sender, header, payload = unpack(data)
        if sender == self.device_id:
            return
        neighbour = self.neighbourhood.admit(header, self.position)
        if neighbour is None:
            return
        self._measured[sender] = [neighbour, 0]
        self._device.receive(sender, payload)

    def run_round(self, time: float) -> bytes:
        """
        Run the program once.

        Args:
            time: The time of the node, in seconds: the ``time`` sensor.

        Returns:
            The bytes to publish on the shared topic.
        """
        payload = self._device.run_round(self._sense(time))
        return pack(self.device_id, self.neighbourhood.header(self.position), payload)

    def _sense(self, time: float) -> dict[str, Any]:
        """
        The sensors of this round.

        ``neighbors_distances`` and ``neighbors_vectors`` hold the measured neighbours, empty
        before any is, when the neighbourhood measures; they are left out when it does not, so
        that the program shares positions instead.
        """
        for sender in list(self._measured):
            self._measured[sender][1] += 1
            if self._measured[sender][1] > self.lifetime:
                del self._measured[sender]
        neighbours: dict[Any, Neighbour] = {
            sender: entry[0] for sender, entry in self._measured.items()
        }
        sensors: dict[str, Any] = {"time": time, "position": None, **self.readings}
        distances = {
            sender: n.distance for sender, n in neighbours.items() if n.distance is not None
        }
        vectors = {sender: n.vector for sender, n in neighbours.items() if n.vector is not None}
        if self.neighbourhood.measures:
            sensors["neighbors_distances"], sensors["neighbors_vectors"] = distances, vectors
        if self.sensors is not None:
            sensors.update(self.sensors())
        return sensors

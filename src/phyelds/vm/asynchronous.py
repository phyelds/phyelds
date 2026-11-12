"""
Asynchronous rounds of many devices in one process: each device sends right after its own
round (a spike), so the next devices to run already read its new message.
"""
from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any

from phyelds.vm import Engine
from phyelds.vm.internal import MutableEngine
from phyelds.vm.rounds import run_round


class AsynchronousRuntime:  # pylint: disable=too-many-instance-attributes
    """
    Runs an aggregate program on many devices, one spike or sequential round at a time.

    When a device runs, it reads the last messages its current neighbors sent and publishes
    its new message right away, so the next devices to run read it in the same step.

    Args:
        program: The ``@aggregate`` function to run on each device.
        retention: For how long, in the units of the ``"time"`` sensor or ``time``, a silent
            device is kept before its state, messages and outputs are forgotten; ``None`` by
            default, which keeps silent devices until ``forget`` or ``reset``.
        paths: Alignment path encoding for the default ``MutableEngine`` (``"compact"`` by
            default).
        engine_factory: Optional factory building the ``Engine`` used to run rounds.

    Raises:
        ValueError: If ``retention`` is not positive.
    """

    def __init__(
        self,
        program: Callable[[], Any],
        *,
        retention: float | None = None,
        paths: Any = "compact",
        engine_factory: Callable[[], Engine] | None = None,
    ):
        if retention is not None and retention <= 0:
            raise ValueError(f"retention must be positive, not {retention}")
        self.program = program
        self.retention = retention
        self._engine: Engine | None = None
        self._factory: Callable[[], Engine] = (
            engine_factory if engine_factory is not None else lambda: MutableEngine(paths=paths)
        )
        self._last_seen: dict[Hashable, float] = {}
        self._states: dict[Hashable, dict[str, Any]] = {}
        self._outboxes: dict[Hashable, dict[str, Any]] = {}
        self.outputs: dict[Hashable, dict[str, Any]] = {}
        """What the program stored with ``store`` on each device, in its last spike."""

    def spike(
        self,
        device: Hashable,
        sensors: Mapping[str, Any],
        neighbors: Iterable[Hashable],
        *,
        time: float | None = None,
    ) -> Any:
        """
        Run the program once on ``device``, keeping the state and messages of the others.

        Args:
            device: The id of the device running the spike.
            sensors: The sensors of ``device`` in this spike, by name.
            neighbors: The ids of the current neighbors of ``device``.
            time: The time of this spike, when it is not in ``sensors["time"]``.

        Returns:
            The result of the program on ``device``.

        Raises:
            ValueError: If ``retention`` is set and neither ``time`` nor ``sensors["time"]``
                is given.
        """
        if time is not None and "time" not in sensors:
            copied_sensors = dict(sensors)
            copied_sensors["time"] = time
            device_sensors: Mapping[str, Any] = copied_sensors
        else:
            device_sensors = sensors
        if self.retention is not None:
            now = device_sensors.get("time")
            if now is None:
                raise ValueError("retention requires a time in sensors or as time=")
            for other, seen in list(self._last_seen.items()):
                if now - seen > self.retention:
                    self.forget(other)
            self._last_seen[device] = now
        if self._engine is None:
            self._engine = self._factory()
        inbox = {other: self._outboxes[other] for other in neighbors if other in self._outboxes}
        done = run_round(
            self.program,
            device,
            device_sensors,
            inbox,
            self._states.get(device),
            engine_instance=self._engine,
        )
        self._states[device], self._outboxes[device] = done.state, done.outbox
        self.outputs[device] = done.outputs
        return done.result

    def run_round(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
        *,
        time: float | None = None,
    ) -> dict[Hashable, Any]:
        """
        Run the program once on each device of ``sensors``, in the order of ``sensors``.

        Args:
            sensors: The sensors of each device of this round, by its id.
            neighbors: The ids of the neighbors of each device, by its id.
            time: The time of this round, when it is not in ``sensors[device]["time"]``.

        Returns:
            The result of the program on each device, by its id, in the order of ``sensors``.
        """
        return {
            device: self.spike(device, device_sensors, neighbors.get(device, ()), time=time)
            for device, device_sensors in sensors.items()
        }

    def forget(self, device: Hashable) -> None:
        """
        Forget the state, the messages and the outputs of ``device``.

        Args:
            device: The id of the device to forget.
        """
        self._states.pop(device, None)
        self._outboxes.pop(device, None)
        self.outputs.pop(device, None)
        self._last_seen.pop(device, None)

    def reset(self) -> None:
        """Forget the state and the messages of every device."""
        self._states, self._outboxes, self.outputs, self._last_seen = {}, {}, {}, {}

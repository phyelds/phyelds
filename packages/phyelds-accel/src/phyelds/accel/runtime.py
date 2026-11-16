"""C-accelerated per-device round helpers and synchronous/asynchronous runtimes."""

from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
# In Python 3.14 concurrent.futures loads ThreadPoolExecutor in __getattr__, which astroid misses.
from concurrent.futures import ThreadPoolExecutor  # pylint: disable=no-name-in-module
import threading
from typing import Any
import weakref

from phyelds import engine
from phyelds.accel.build import load_extension
from phyelds.vm.asynchronous import AsynchronousRuntime as _BaseAsynchronousRuntime
from phyelds.vm.rounds import Round
from phyelds.vm.synchronous import (
    SynchronousRuntime as _BaseSynchronousRuntime,
    _chunks,
    _merge,
)

_ChunkResult = tuple[
    dict[Hashable, Any], dict[Hashable, Any], dict[Hashable, Any], dict[Hashable, Any]
]


def run_round(
    program: Callable[[], Any],
    device: Hashable,
    sensors: Mapping[str, Any],
    inbox: Mapping[Hashable, Mapping[int, Any]],
    state: Mapping[int, Any] | None = None,
) -> Round:
    """Run ``program`` once on ``device`` using the C ``NativeEngine`` (compact keys).

    Args:
        program: The ``@aggregate`` function to run.
        device: The ID of the device.
        sensors: Sensor readings for ``device`` in this round.
        inbox: Neighbor outboxes keyed by neighbor ID.
        state: State dictionary from the previous round, or ``None``.

    Returns:
        The ``Round`` result, compact-keyed outbox, updated state and stored outputs.
    """
    ext = load_extension()
    native_engine = ext.NativeEngine()
    context = ext.NativeNodeContext(device, sensors)
    engine.set(native_engine)
    native_engine.setup(context, inbox, state)
    result = program()
    outbox = native_engine.cooldown()
    return Round(
        result=result,
        outbox=outbox,
        state=native_engine.state_trace(),
        outputs=context.outputs,
    )


class SynchronousRuntime(_BaseSynchronousRuntime):
    """C-accelerated drop-in counterpart of ``phyelds.vm.synchronous.SynchronousRuntime``."""

    def __init__(self, program: Callable[[], Any], *, workers: int = 1) -> None:
        super().__init__(program, workers=workers)
        self._ext = load_extension()
        self._local = threading.local()
        self._pool: ThreadPoolExecutor | None = None
        self._finalizer: weakref.finalize | None = None

    def run_round(
        self,
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> dict[Hashable, Any]:
        """Run ``program`` synchronously once on every device in ``sensors``."""
        devices = list(sensors)
        if self.workers == 1:
            self._states, self._outboxes, self.outputs, results = self._run_native(
                devices, sensors, neighbors
            )
            return results

        pool = self._ensure_pool()
        chunks = _chunks(devices, self.workers)
        parts = list(pool.map(lambda chunk: self._run_native(chunk, sensors, neighbors), chunks))
        self._states, self._outboxes, self.outputs, results = _merge(parts)
        return results

    def close(self) -> None:
        """Shut down the worker thread pool, if one was started."""
        if self._finalizer is not None:
            self._finalizer()
            self._finalizer = None
        self._pool = None

    def _ensure_pool(self) -> ThreadPoolExecutor:
        if self._pool is None:
            pool = ThreadPoolExecutor(self.workers)
            self._pool = pool
            self._finalizer = weakref.finalize(self, pool.shutdown, wait=False)
        return self._pool

    def _run_native(
        self,
        devices: Sequence[Hashable],
        sensors: Mapping[Hashable, Mapping[str, Any]],
        neighbors: Mapping[Hashable, Iterable[Hashable]],
    ) -> _ChunkResult:
        pair = getattr(self._local, "pair", None)
        if pair is None:
            pair = (self._ext.NativeEngine(), self._ext.NativeNodeContext(0, {}))
            self._local.pair = pair
        eng, ctx = pair
        return self._ext.run_chunk(
            eng, ctx, engine, self.program, devices, sensors, neighbors,
            self._outboxes, self._states,
        )


class AsynchronousRuntime(_BaseAsynchronousRuntime):
    """C-accelerated drop-in counterpart of ``phyelds.vm.asynchronous.AsynchronousRuntime``."""

    def __init__(
        self, program: Callable[[], Any], *, retention: float | None = None
    ) -> None:
        super().__init__(program, retention=retention)
        ext = load_extension()
        self._native_engine = ext.NativeEngine()
        self._native_context = ext.NativeNodeContext(0, {})

    def spike(
        self,
        device: Hashable,
        sensors: Mapping[str, Any],
        neighbors: Iterable[Hashable],
        *,
        time: float | None = None,
    ) -> Any:
        """Run ``program`` once on ``device``, publishing its new outbox immediately."""
        device_sensors = self._prepare_spike_sensors(device, sensors, time)
        inbox = {other: self._outboxes[other] for other in neighbors if other in self._outboxes}
        self._native_context.node_id = device
        self._native_context.sensors = device_sensors
        self._native_context.outputs = None
        engine.set(self._native_engine)
        self._native_engine.setup(self._native_context, inbox, self._states.get(device))
        result = self.program()
        outbox = self._native_engine.cooldown()
        self._states[device] = self._native_engine.state_trace()
        self._outboxes[device] = outbox
        self.outputs[device] = self._native_context.outputs
        return result

    def _prepare_spike_sensors(
        self, device: Hashable, sensors: Mapping[str, Any], time: float | None
    ) -> Mapping[str, Any]:
        resolved: Mapping[str, Any] = (
            {**sensors, "time": time} if time is not None and "time" not in sensors else sensors
        )
        if self.retention is None:
            return resolved
        timestamp = resolved.get("time")
        if timestamp is None:
            raise ValueError("retention requires a time in sensors or as time=")
        expired = [
            peer for peer, seen in self._last_seen.items() if timestamp - seen > self.retention
        ]
        for peer in expired:
            self.forget(peer)
        self._last_seen[device] = timestamp
        return resolved

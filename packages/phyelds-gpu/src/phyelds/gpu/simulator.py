"""GPU/CPU concurrent-wavefront and synchronous runtimes for ``@aggregate`` programs."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import math
from typing import Any

import torch

from phyelds import engine
from phyelds.gpu.engine import BatchEngine, WorldStore, _alloc_like
from phyelds.gpu.fields import _as_node_tensor, _promote_pair
from phyelds.gpu.topology import GraphTopology, SubbatchEdges, radius_topology
from phyelds.vm.wavefront import (
    Channel,
    Clock,
    ExponentialClock,
    PeriodicClock,
    WeibullClock,
)


def _tensor_to_python_list(value: Any, count: int) -> list[Any]:
    if value is None:
        return [None] * count
    if isinstance(value, tuple):
        parts = [_tensor_to_python_list(item, count) for item in value]
        return [tuple(col[idx] for col in parts) for idx in range(count)]
    if isinstance(value, torch.Tensor):
        expanded = value if value.ndim > 0 else value.expand(count)
        return expanded.detach().cpu().tolist()
    return [value] * count


def _pack_dict_sensors(
    sensors: Mapping[int, Mapping[str, Any]],
    devices: list[int],
    target_device: torch.device,
) -> dict[str, torch.Tensor]:
    if not devices:
        return {}
    names: set[str] = set()
    for dev in devices:
        names.update(sensors[dev].keys())
    packed: dict[str, torch.Tensor] = {}
    for name in names:
        raw = [sensors[dev].get(name) for dev in devices]
        if any(item is None for item in raw):
            continue
        first = raw[0]
        if isinstance(first, bool):
            packed[name] = torch.tensor(raw, dtype=torch.bool, device=target_device)
        elif isinstance(first, int):
            packed[name] = torch.tensor(raw, dtype=torch.int64, device=target_device)
        else:
            packed[name] = torch.tensor(raw, dtype=torch.float64, device=target_device)
    return packed


def _normalize_tensor_sensors(
    sensors: Mapping[str, Any], num_nodes: int, target_device: torch.device
) -> dict[str, torch.Tensor]:
    out: dict[str, torch.Tensor] = {}
    for name, val in sensors.items():
        if isinstance(val, torch.Tensor):
            out[name] = val.to(device=target_device)
        else:
            out[name] = _as_node_tensor(val, num_nodes, target_device)
    return out


class GpuSynchronousRuntime:
    """
    Synchronous whole-network runtime executing ``@aggregate`` programs on PyTorch CPU or CUDA.

    Accepts either standard Python dictionaries ``(sensors, neighbors)`` (drop-in compatible
    with ``phyelds.vm.synchronous.SynchronousRuntime``) or pre-built ``GraphTopology`` and
    tensor sensor dictionaries via ``run_tensor_round``.

    Args:
        program: The ``@aggregate`` function to execute.
        device: Torch device (e.g. ``"cuda"`` or ``"cpu"``).
    """

    def __init__(
        self, program: Callable[[], Any], *, device: torch.device | str = "cpu"
    ) -> None:
        self.program = program
        self.device = torch.device(device)
        self.outputs: dict[Any, dict[str, Any]] = {}
        self._store: WorldStore | None = None
        self._cached_key: tuple[Any, ...] | None = None
        self._idx_to_id: list[Any] = []
        self._tick = 0.0

    def reset(self) -> None:
        """Forget all device states, outboxes and outputs."""
        self.outputs = {}
        self._store = None
        self._cached_key = None
        self._tick = 0.0

    def run_tensor_round(
        self,
        topology: GraphTopology,
        sensors: Mapping[str, Any],
        *,
        positions: torch.Tensor | None = None,
    ) -> Any:
        """Execute one synchronous round directly on GPU/CPU tensors."""
        if self._store is None or self._store.topology is not topology:
            self._store = WorldStore(topology=topology, channel=Channel(delay=0.5))
            self._tick = 0.0

        packed = _normalize_tensor_sensors(sensors, topology.num_nodes, self.device)
        batch_times = torch.full(
            (topology.num_nodes,), self._tick, dtype=torch.float64, device=self.device
        )
        batch_eng = BatchEngine(
            self._store, topology.full_batch(), batch_times, packed, positions=positions
        )
        token = engine.set(batch_eng)
        try:
            result = self.program()
            batch_eng.finish_batch()
        finally:
            engine.reset(token)
        self._tick += 1.0
        return result

    def run_round(
        self,
        sensors: Mapping[Any, Mapping[str, Any]],
        neighbors: Mapping[Any, Iterable[Any]],
    ) -> dict[Any, Any]:
        """Drop-in ``SynchronousRuntime.run_round`` wrapper converting Python dicts."""
        devices = list(sensors)
        if not devices:
            self.reset()
            return {}

        id_map = {dev: idx for idx, dev in enumerate(devices)}
        int_neighbors = {
            id_map[dev]: tuple(
                sorted(id_map[p] for p in neighbors.get(dev, ()) if p in id_map and p != dev)
            )
            for dev in devices
        }
        topo_sig = (tuple(devices), tuple(int_neighbors.items()))
        if topo_sig != self._cached_key or self._store is None:
            if tuple(devices) != tuple(self._idx_to_id):
                self._store = None
                self._tick = 0.0
            topo = GraphTopology.from_neighbors(
                int_neighbors, num_nodes=len(devices), device=self.device
            )
            if self._store is None:
                self._store = WorldStore(topology=topo, channel=Channel(delay=0.5))
            else:
                self._store.topology = topo
            self._cached_key = topo_sig
            self._idx_to_id = devices

        idx_sensors = {id_map[dev]: sensors[dev] for dev in devices}
        packed = _pack_dict_sensors(idx_sensors, list(range(len(devices))), self.device)
        raw_res = self.run_tensor_round(self._store.topology, packed)

        py_vals = _tensor_to_python_list(raw_res, len(devices))
        self.outputs = self._export_outputs(devices)
        return dict(zip(devices, py_vals))

    def _export_outputs(self, devices: list[Any]) -> dict[Any, dict[str, Any]]:
        assert self._store is not None
        out: dict[Any, dict[str, Any]] = {dev: {} for dev in devices}
        for name, (buf, valid) in self._store.outputs.items():
            vals = buf.detach().cpu().tolist()
            flags = valid.detach().cpu().tolist()
            for idx, dev in enumerate(devices):
                if flags[idx]:
                    out[dev][name] = vals[idx]
        return out


@dataclass(frozen=True)
class GpuWavefrontStep:
    """Metadata of one concurrent batch executed by ``GpuWavefrontRuntime``."""

    time: float
    batch_ids: torch.Tensor

    @property
    def devices(self) -> tuple[int, ...]:
        """Tuple of device IDs executed concurrently in this wavefront."""
        return tuple(self.batch_ids.detach().cpu().tolist())


class GpuWavefrontRuntime:  # pylint: disable=too-many-instance-attributes
    """
    GPU/CPU concurrent-batch discrete-event simulator approximating decentralized async systems.

    Selects causally independent wavefronts directly on the Torch device:
    - When ``channel.delay == 0`` and ``window == 0``, wavefronts are exact conservative DES
      batches matching single-event sequential execution.
    - With realistic clocks (``WeibullClock``, ``PeriodicClock(random_phase=True, drift=...)``)
      and positive radio ``delay`` / ``loss`` / ``retention``, concurrent nodes within the
      latency window execute together on the GPU, generate in-flight messages, and advance.
    - In the synchronous worst case (aligned clocks and ``delay > 0`` or ``window > 0``),
      each batch spans all ``N`` nodes in a single GPU pass.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        program: Callable[[], Any],
        *,
        topology: GraphTopology | None = None,
        positions: torch.Tensor | None = None,
        radius: float | None = None,
        clock: Clock | None = None,
        channel: Channel | None = None,
        window: float | None = None,
        seed: int = 0,
        device: torch.device | str = "cpu",
    ) -> None:
        if topology is None:
            if positions is None or radius is None:
                raise ValueError("provide either topology= or both positions= and radius=")
            target_dev = torch.device(device)
            pos_t = positions.to(device=target_dev, dtype=torch.float64)
            topology = radius_topology(pos_t, radius)
            positions = pos_t
        else:
            target_dev = topology.device
            if positions is not None:
                positions = positions.to(device=target_dev, dtype=torch.float64)
        if window is not None and window < 0:
            raise ValueError(f"window must be non-negative, not {window}")

        self.program = program
        self.topology = topology
        self.positions = positions
        self.clock: Clock = PeriodicClock(1.0) if clock is None else clock
        self.channel: Channel = Channel() if channel is None else channel
        self.window = window
        self.seed = seed
        self.device = target_dev

        self._rng = torch.Generator(device=self.device)
        self._rng.manual_seed(seed)
        self._store = WorldStore(topology=self.topology, channel=self.channel)
        self._next_time = torch.zeros(topology.num_nodes, dtype=torch.float64, device=self.device)
        self._last_time = torch.full(
            (topology.num_nodes,), math.nan, dtype=torch.float64, device=self.device
        )
        self._skew = torch.ones(topology.num_nodes, dtype=torch.float64, device=self.device)
        self._result_buf: Any = None
        self._result_valid = torch.zeros(topology.num_nodes, dtype=torch.bool, device=self.device)
        self._init_clocks()

    def _init_clocks(self) -> None:
        n = self.topology.num_nodes
        if n == 0:
            return
        self._rng.manual_seed(self.seed)
        if isinstance(self.clock, PeriodicClock):
            if self.clock.drift > 0.0:
                u_skew = torch.rand(n, generator=self._rng, device=self.device, dtype=torch.float64)
                self._skew = 1.0 + (2.0 * u_skew - 1.0) * self.clock.drift
            if self.clock.random_phase:
                u = torch.rand(n, generator=self._rng, device=self.device, dtype=torch.float64)
                self._next_time = self.clock.period * (1.0 - u)
            else:
                self._next_time.zero_()
        elif isinstance(self.clock, WeibullClock):
            if self.clock.random_phase:
                u = torch.rand(n, generator=self._rng, device=self.device, dtype=torch.float64)
                self._next_time = self.clock.period * (1.0 - u)
            else:
                self._next_time.zero_()
        elif isinstance(self.clock, ExponentialClock):
            self._next_time = self._sample_deltas(torch.arange(n, device=self.device))
        else:
            self._next_time.zero_()

    def _sample_deltas(self, batch_ids: torch.Tensor) -> torch.Tensor:
        m = int(batch_ids.numel())
        if isinstance(self.clock, PeriodicClock):
            noise = 1.0
            if self.clock.jitter > 0.0:
                u = torch.rand(m, generator=self._rng, device=self.device, dtype=torch.float64)
                noise = 1.0 + (2.0 * u - 1.0) * self.clock.jitter
            return torch.clamp_min(self.clock.period * self._skew[batch_ids] * noise, 1e-12)
        if isinstance(self.clock, WeibullClock):
            u = torch.clamp(
                torch.rand(m, generator=self._rng, device=self.device, dtype=torch.float64),
                1e-15,
                1.0 - 1e-15,
            )
            scale = self.clock.period / math.gamma(1.0 + 1.0 / self.clock.shape)
            return torch.clamp_min(scale * (-torch.log1p(-u)) ** (1.0 / self.clock.shape), 1e-12)
        if isinstance(self.clock, ExponentialClock):
            u = torch.clamp(
                torch.rand(m, generator=self._rng, device=self.device, dtype=torch.float64),
                1e-15,
                1.0 - 1e-15,
            )
            return torch.clamp_min(-torch.log1p(-u) / self.clock.rate, 1e-12)
        return torch.ones(m, dtype=torch.float64, device=self.device)

    def set_next_times(self, next_times: torch.Tensor) -> None:
        """Explicitly set device wakeup timestamps (`float64 [N]`)."""
        self._next_time = next_times.to(device=self.device, dtype=torch.float64).clone()

    def earliest_time(self) -> float:
        """Return the minimum pending wakeup timestamp across all devices."""
        if self.topology.num_nodes == 0:
            return math.inf
        return float(self._next_time.min().item())

    def last_time_of(self, node_id: int) -> float:
        """Return the timestamp at which ``node_id`` last executed."""
        return float(self._last_time[node_id].item())

    def reset(self) -> None:
        """Reset states, messages, outputs, results and clocks back to time zero."""
        self._store.reset()
        self._last_time.fill_(math.nan)
        self._result_buf = None
        self._result_valid.zero_()
        self._init_clocks()

    def select_wavefront(self, *, until: float | None = None) -> torch.Tensor:
        """Select the concurrent ``int64 [M]`` node IDs eligible to execute in the next batch."""
        n = self.topology.num_nodes
        if n == 0:
            return torch.zeros(0, dtype=torch.int64, device=self.device)
        earliest = self._next_time.min()
        if until is not None and float(earliest.item()) > until:
            return torch.zeros(0, dtype=torch.int64, device=self.device)

        horizon = getattr(self.clock, "horizon", math.inf)
        cap_val = float(earliest.item()) + horizon
        if until is not None:
            cap_val = min(cap_val, until)
        eligible = self._next_time <= cap_val

        snd = self.topology.sender
        rcv = self.topology.receiver
        if snd.numel() > 0:
            eff_delay = max(self.channel.delay, 0.0 if self.window is None else self.window)
            t_s = self._next_time[snd]
            t_r = self._next_time[rcv]
            if eff_delay > 0.0:
                blocked_edge = (t_s + eff_delay) < t_r
            else:
                blocked_edge = (t_s < t_r) | ((t_s == t_r) & (snd < rcv))
            is_blocked = torch.zeros(n, dtype=torch.bool, device=self.device)
            is_blocked[rcv[blocked_edge]] = True
            eligible = eligible & (~is_blocked)

        return torch.nonzero(eligible, as_tuple=False).squeeze(-1)

    def step(
        self, sensors: Mapping[str, Any], *, until: float | None = None
    ) -> GpuWavefrontStep:
        """Select and execute the next concurrent batch of devices on the Torch device."""
        batch_ids = self.select_wavefront(until=until)
        if batch_ids.numel() == 0:
            return GpuWavefrontStep(time=until or 0.0, batch_ids=batch_ids)

        n = self.topology.num_nodes
        packed = _normalize_tensor_sensors(sensors, n, self.device)
        batch_times = self._next_time[batch_ids]
        edges: SubbatchEdges = (
            self.topology.full_batch()
            if int(batch_ids.numel()) == n
            else self.topology.subbatch(batch_ids)
        )

        batch_eng = BatchEngine(
            self._store,
            edges,
            batch_times,
            packed,
            positions=self.positions,
            rng=self._rng,
        )
        token = engine.set(batch_eng)
        try:
            batch_res = self.program()
            batch_eng.finish_batch()
        finally:
            engine.reset(token)

        self._record_results(batch_ids, batch_res)
        self._last_time[batch_ids] = batch_times
        self._next_time[batch_ids] = batch_times + self._sample_deltas(batch_ids)
        return GpuWavefrontStep(time=float(batch_times.max().item()), batch_ids=batch_ids)

    def run_until(self, until: float, sensors: Mapping[str, Any]) -> dict[int, Any]:
        """Advance concurrent wavefronts until ``earliest_time() > until``."""
        while self.earliest_time() <= until:
            executed = self.step(sensors, until=until)
            if executed.batch_ids.numel() == 0:
                break
        return self.results()

    def _record_results(self, batch_ids: torch.Tensor, batch_res: Any) -> None:
        n = self.topology.num_nodes
        m = int(batch_ids.numel())
        if isinstance(batch_res, tuple):
            if self._result_buf is None:
                self._result_buf = [None] * len(batch_res)
            for idx, item in enumerate(batch_res):
                t_item = _as_node_tensor(item, m, self.device)
                if self._result_buf[idx] is None:
                    self._result_buf[idx] = _alloc_like(t_item, n)
                else:
                    buf, t_item = _promote_pair(self._result_buf[idx], t_item)
                    self._result_buf[idx] = buf
                self._result_buf[idx][batch_ids] = t_item
        else:
            t_item = _as_node_tensor(batch_res, m, self.device)
            if self._result_buf is None:
                self._result_buf = _alloc_like(t_item, n)
            else:
                buf, t_item = _promote_pair(self._result_buf, t_item)
                self._result_buf = buf
            self._result_buf[batch_ids] = t_item
        self._result_valid[batch_ids] = True

    def results_tensor(self) -> Any:
        """Return the raw GPU/CPU result tensor (or tuple of tensors) across ``0..N-1``."""
        if isinstance(self._result_buf, list):
            return tuple(self._result_buf)
        return self._result_buf

    def results(self) -> dict[int, Any]:
        """Materialize results of all devices that have executed at least once as a Python dict."""
        if self._result_buf is None:
            return {}
        n = self.topology.num_nodes
        valid = self._result_valid.detach().cpu().tolist()
        raw = (
            tuple(self._result_buf) if isinstance(self._result_buf, list) else self._result_buf
        )
        as_list = _tensor_to_python_list(raw, n)
        return {nid: as_list[nid] for nid in range(n) if valid[nid]}

    def outputs(self) -> dict[int, dict[str, Any]]:
        """Materialize ``store(...)`` outputs of devices that have executed at least once."""
        n = self.topology.num_nodes
        ran = self._result_valid.detach().cpu().tolist()
        out: dict[int, dict[str, Any]] = {nid: {} for nid in range(n) if ran[nid]}
        for name, (buf, valid) in self._store.outputs.items():
            vals = buf.detach().cpu().tolist()
            flags = valid.detach().cpu().tolist()
            for nid in out:
                if flags[nid]:
                    out[nid][name] = vals[nid]
        return out

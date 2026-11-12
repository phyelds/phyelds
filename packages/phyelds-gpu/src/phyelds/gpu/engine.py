"""VRAM state/channel store and SPMD ``BatchEngine`` executing concurrent device batches."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import math
from typing import Any

import torch

from phyelds.calculus import exchange as _calculus_exchange, neighbors as _calculus_neighbors
from phyelds.gpu.fields import BatchedNeighborhoodField, _as_node_tensor, _promote_pair
from phyelds.gpu.topology import GraphTopology, SubbatchEdges
from phyelds.gpu.transform import compile_for_gpu, merge_branch_values
from phyelds.vm import Engine
from phyelds.vm.internal import CompactPaths
from phyelds.vm.wavefront import Channel

_NEIGHBORS_RAW = _calculus_neighbors.__wrapped__
_EXCHANGE_RAW = _calculus_exchange.__wrapped__


def _alloc_like(sample: torch.Tensor, size: int) -> torch.Tensor:
    shape = (size, *sample.shape[1:])
    return torch.zeros(shape, dtype=sample.dtype, device=sample.device)


def _select_rows(cond: torch.Tensor, if_true: torch.Tensor, if_false: torch.Tensor) -> torch.Tensor:
    expanded = cond.unsqueeze(-1) if if_true.ndim > 1 else cond
    return torch.where(expanded, if_true, if_false)


@dataclass
class _SiteState:
    """Global per-node state buffer for one alignment path key."""

    values: torch.Tensor
    valid: torch.Tensor


@dataclass
class _OutboxBuffer:
    """Double-buffered `(committed, pending)` message values and validity masks."""

    committed_val: torch.Tensor
    committed_valid: torch.Tensor
    pending_val: torch.Tensor
    pending_valid: torch.Tensor


@dataclass
class WorldStore:  # pylint: disable=too-many-instance-attributes
    """Persistent VRAM buffers for all ``N`` nodes and ``E`` edges across wavefront steps."""

    topology: GraphTopology
    channel: Channel = field(default_factory=Channel)
    states: dict[int, _SiteState] = field(default_factory=dict)
    node_outboxes: dict[int, _OutboxBuffer] = field(default_factory=dict)
    edge_outboxes: dict[int, _OutboxBuffer] = field(default_factory=dict)
    node_committed_at: torch.Tensor = field(init=False)
    node_pending_at: torch.Tensor = field(init=False)
    edge_committed_at: torch.Tensor | None = field(init=False, default=None)
    edge_pending_at: torch.Tensor | None = field(init=False, default=None)
    outputs: dict[str, tuple[torch.Tensor, torch.Tensor]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n_nodes = self.topology.num_nodes
        dev = self.topology.device
        self.node_committed_at = torch.full((n_nodes,), -math.inf, dtype=torch.float64, device=dev)
        self.node_pending_at = torch.full((n_nodes,), math.inf, dtype=torch.float64, device=dev)
        if self.uses_edge_slots:
            n_edges = int(self.topology.sender.numel())
            self.edge_committed_at = torch.full(
                (n_edges,), -math.inf, dtype=torch.float64, device=dev
            )
            self.edge_pending_at = torch.full(
                (n_edges,), math.inf, dtype=torch.float64, device=dev
            )

    @property
    def uses_edge_slots(self) -> bool:
        """True when per-link randomness (`loss > 0` or `jitter > 0`) requires edge slots."""
        return self.channel.loss > 0.0 or self.channel.jitter > 0.0

    def reset(self) -> None:
        """Clear all stored states, outboxes and outputs."""
        self.states.clear()
        self.node_outboxes.clear()
        self.edge_outboxes.clear()
        self.outputs.clear()
        self.node_committed_at.fill_(-math.inf)
        self.node_pending_at.fill_(math.inf)
        if self.edge_committed_at is not None and self.edge_pending_at is not None:
            self.edge_committed_at.fill_(-math.inf)
            self.edge_pending_at.fill_(math.inf)


class BatchNodeContext:
    """Vectorized ``NodeContext`` exposing batch slices of device IDs, sensors and outputs."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        engine_ref: "BatchEngine",
        batch_ids: torch.Tensor,
        batch_times: torch.Tensor,
        sensors: Mapping[str, torch.Tensor],
        positions: torch.Tensor | None,
    ) -> None:
        self._engine = engine_ref
        self.node_id = batch_ids
        self._times = batch_times
        self._sensors = sensors
        self._positions = positions
        self.batch_outputs: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}

    def sense(self, sensor_name: str) -> Any:
        """Read ``sensor_name`` for the ``M`` devices in the active batch."""
        if sensor_name == "time" and "time" not in self._sensors:
            return self._times
        if sensor_name == "position" and "position" not in self._sensors:
            return None if self._positions is None else self._positions[self.node_id]
        tensor = self._sensors.get(sensor_name)
        return None if tensor is None else tensor[self.node_id]

    def position(self) -> Any:
        """Return positions (`[M, D]`) of the active batch."""
        return self.sense("position")

    def time(self) -> torch.Tensor:
        """Return timestamps (`[M]`) of the active batch."""
        sensed = self.sense("time")
        return self._times if sensed is None else sensed

    def store(self, output_name: str, value: Any) -> None:
        """Write ``value`` to ``output_name`` for the currently active branch lanes."""
        mask = self._engine.active_mask
        if not bool(mask.any().item()):
            return
        val_t = _as_node_tensor(value, self._engine.batch_size, self._engine.device)
        existing = self.batch_outputs.get(output_name)
        if existing is None:
            buf = _alloc_like(val_t, self._engine.batch_size)
            buf[mask] = val_t[mask]
            self.batch_outputs[output_name] = (buf, mask.clone())
        else:
            prev_buf, prev_mask = existing
            prev_buf, val_t = _promote_pair(prev_buf, val_t)
            merged_buf = _select_rows(mask, val_t, prev_buf)
            self.batch_outputs[output_name] = (merged_buf, prev_mask | mask)


class BatchEngine(Engine):  # pylint: disable=too-many-instance-attributes
    """SPMD ``Engine`` executing an ``@aggregate`` program across a concurrent batch ``B``."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        store: WorldStore,
        edges: SubbatchEdges,
        batch_times: torch.Tensor,
        sensors: Mapping[str, torch.Tensor],
        *,
        positions: torch.Tensor | None = None,
        rng: torch.Generator | None = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.edges = edges
        self.batch_size = edges.batch_size
        self.device = store.topology.device
        self.batch_times = batch_times
        self._rng = rng
        self._paths = CompactPaths()
        self._stack: list[int] = []
        self._counts: list[int] = [0]
        self.active_mask = torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
        self._read_masks: dict[int, torch.Tensor] = {}
        self._sent: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
        self.node_context = BatchNodeContext(  # type: ignore[assignment]
            self, edges.batch_ids, batch_times, sensors, positions
        )

    def enter(self, name: str) -> None:
        counter = self._counts[-1]
        self._counts[-1] = counter + 1
        parent = self._stack[-1] if self._stack else None
        self._stack.append(self._paths.segment(parent, name, counter))
        self._counts.append(0)

    def exit(self) -> None:
        if self._stack:
            self._stack.pop()
            self._counts.pop()

    def current_key(self) -> int:
        """Compact 30-bit integer key of the current alignment path."""
        return self._paths.key(self._stack)

    def _run_under_mask(self, name: str, mask: torch.Tensor, fn: Callable[[], Any]) -> Any:
        saved = self.active_mask
        self.enter(name)
        try:
            if not bool(mask.any().item()):
                return None
            self.active_mask = mask
            return fn()
        finally:
            self.active_mask = saved
            self.exit()

    def _run_aggregate(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        raw = getattr(func, "__wrapped__", func)
        if raw is _NEIGHBORS_RAW:
            return self._exec_neighbors(*args, **kwargs)
        if raw is _EXCHANGE_RAW:
            return self._exec_exchange(*args, **kwargs)
        compiled = compile_for_gpu(raw)
        self.enter(func.__name__)
        try:
            return compiled(*args, **kwargs)
        finally:
            self.exit()

    def _branch(
        self, condition: Any, if_true: Callable[[], Any], if_false: Callable[[], Any]
    ) -> Any:
        cond = _as_node_tensor(condition, self.batch_size, self.device, dtype=torch.bool)
        left_mask = self.active_mask & cond
        right_mask = self.active_mask & (~cond)
        left_val = self._run_under_mask("left", left_mask, if_true)
        right_val = self._run_under_mask("right", right_mask, if_false)
        if not bool(left_mask.any().item()):
            return right_val
        if not bool(right_mask.any().item()):
            return left_val
        return merge_branch_values(cond, left_val, right_val, self.batch_size, self.device)

    def execute_if_statement(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        condition: Any,
        state_vars: tuple[Any, ...],
        left_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]],
        right_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]],
        after_fn: Callable[..., tuple[bool, Any, tuple[Any, ...]]] | None,
    ) -> tuple[bool, Any, tuple[Any, ...]]:
        """Run a statement-level ``if/else`` + continuation with SSA local variable merging."""
        cond = _as_node_tensor(condition, self.batch_size, self.device, dtype=torch.bool)
        saved_mask = self.active_mask
        left_mask = saved_mask & cond
        right_mask = saved_mask & (~cond)
        left_out = self._run_under_mask("left", left_mask, lambda: left_fn(*state_vars))
        right_out = self._run_under_mask("right", right_mask, lambda: right_fn(*state_vars))
        left_ret, left_val, left_vars = (False, None, state_vars) if left_out is None else left_out
        right_ret, right_val, right_vars = (
            (False, None, state_vars) if right_out is None else right_out
        )

        merged_vars = tuple(
            merge_branch_values(
                left_mask,
                lv,
                merge_branch_values(right_mask, rv, sv, self.batch_size, self.device),
                self.batch_size,
                self.device,
            )
            for sv, lv, rv in zip(state_vars, left_vars, right_vars)
        )

        if left_ret and right_ret:
            return (
                True,
                merge_branch_values(cond, left_val, right_val, self.batch_size, self.device),
                merged_vars,
            )

        ret_mask = (left_mask if left_ret else torch.zeros_like(cond)) | (
            right_mask if right_ret else torch.zeros_like(cond)
        )
        remaining = saved_mask & (~ret_mask)
        if after_fn is None or not bool(remaining.any().item()):
            if left_ret:
                return True, left_val, merged_vars
            return ((True, right_val) if right_ret else (False, None)) + (merged_vars,)

        self.active_mask = remaining
        try:
            after_ret, after_val, after_vars = after_fn(*merged_vars)
        finally:
            self.active_mask = saved_mask
        final_vars = tuple(
            merge_branch_values(remaining, av, mv, self.batch_size, self.device)
            for mv, av in zip(merged_vars, after_vars)
        )
        if not left_ret and not right_ret:
            return after_ret, after_val, final_vars
        chosen_mask = left_mask if left_ret else right_mask
        chosen_val = left_val if left_ret else right_val
        return (
            True,
            merge_branch_values(chosen_mask, chosen_val, after_val, self.batch_size, self.device),
            final_vars,
        )

    def remember_state(self, init: Any) -> tuple[torch.Tensor, Callable[[Any], torch.Tensor]]:
        """Vectorized ``remember(init)`` with per-lane initialization and masked updates."""
        self.enter("remember")
        key = self.current_key()
        self.exit()
        current = self._read_or_init_state(key, init)
        return current, lambda new_value: self._write_masked_state(key, new_value)

    def remember_and_evolve_state(
        self, init: Any, evolve_fn: Callable[[Any], Any]
    ) -> torch.Tensor:
        """Vectorized ``remember_and_evolve(init, evolve_fn)``."""
        key = self.current_key()
        current = self._read_or_init_state(key, init)
        return self._write_masked_state(key, evolve_fn(current))

    def _read_or_init_state(self, key: int, init: Any) -> torch.Tensor:
        init_t = _as_node_tensor(init, self.batch_size, self.device)
        prev_read = self._read_masks.get(key)
        self._read_masks[key] = (
            self.active_mask.clone() if prev_read is None else (prev_read | self.active_mask)
        )

        slot = self.store.states.get(key)
        batch_ids = self.edges.batch_ids
        active_ids = batch_ids[self.active_mask]
        if slot is None:
            buf = _alloc_like(init_t, self.store.topology.num_nodes)
            valid = torch.zeros(self.store.topology.num_nodes, dtype=torch.bool, device=self.device)
            buf[active_ids] = init_t[self.active_mask]
            valid[active_ids] = True
            self.store.states[key] = _SiteState(buf, valid)
            return init_t

        stored_slice, init_t = _promote_pair(slot.values[batch_ids], init_t)
        if slot.values.dtype != stored_slice.dtype:
            slot.values = slot.values.to(dtype=stored_slice.dtype)
        resolved = _select_rows(slot.valid[batch_ids], stored_slice, init_t)
        slot.values[active_ids] = resolved[self.active_mask]
        slot.valid[active_ids] = True
        return resolved

    def _write_masked_state(self, key: int, new_value: Any) -> torch.Tensor:
        val_t = _as_node_tensor(new_value, self.batch_size, self.device)
        slot = self.store.states[key]
        if slot.values.dtype != val_t.dtype:
            common = torch.promote_types(slot.values.dtype, val_t.dtype)
            slot.values = slot.values.to(dtype=common)
            val_t = val_t.to(dtype=common)
        active_ids = self.edges.batch_ids[self.active_mask]
        slot.values[active_ids] = val_t[self.active_mask]
        slot.valid[active_ids] = True
        return val_t

    def _queue_send(self, key: int, value: torch.Tensor) -> None:
        existing = self._sent.get(key)
        if existing is None:
            self._sent[key] = (value, self.active_mask.clone())
        else:
            prev_val, prev_mask = existing
            prev_val, value = _promote_pair(prev_val, value)
            merged_val = _select_rows(self.active_mask, value, prev_val)
            self._sent[key] = (merged_val, prev_mask | self.active_mask)

    def _read_slot_at_indices(
        self,
        slot: _OutboxBuffer,
        indices: torch.Tensor,
        pend_at: torch.Tensor,
        comm_at: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        rx_times = self.batch_times[self.edges.local_receiver]
        pend_arr = pend_at[indices]
        comm_arr = comm_at[indices]
        use_pend = pend_arr <= rx_times
        vals = _select_rows(use_pend, slot.pending_val[indices], slot.committed_val[indices])
        arr_time = torch.where(use_pend, pend_arr, comm_arr)
        valid = torch.where(use_pend, slot.pending_valid[indices], slot.committed_valid[indices])
        valid = valid & (arr_time <= rx_times)
        retention = self.store.channel.retention
        if retention is not None:
            valid = valid & ((rx_times - arr_time) <= retention)
        return vals, valid

    def _gather_incoming(
        self, key: int, sample_local: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        edge_count = int(self.edges.edge_indices.numel())
        if edge_count == 0:
            return sample_local[:0], torch.zeros(0, dtype=torch.bool, device=self.device)
        if self.store.uses_edge_slots:
            eslot = self.store.edge_outboxes.get(key)
            if eslot is None:
                return _alloc_like(sample_local, edge_count), torch.zeros(
                    edge_count, dtype=torch.bool, device=self.device
                )
            assert self.store.edge_pending_at is not None
            assert self.store.edge_committed_at is not None
            return self._read_slot_at_indices(
                eslot,
                self.edges.edge_indices,
                self.store.edge_pending_at,
                self.store.edge_committed_at,
            )
        nslot = self.store.node_outboxes.get(key)
        if nslot is None:
            return _alloc_like(sample_local, edge_count), torch.zeros(
                edge_count, dtype=torch.bool, device=self.device
            )
        return self._read_slot_at_indices(
            nslot,
            self.edges.global_sender,
            self.store.node_pending_at,
            self.store.node_committed_at,
        )

    def _exec_neighbors(self, value: Any) -> BatchedNeighborhoodField:
        if isinstance(value, BatchedNeighborhoodField):
            raise TypeError("Neighborhood is not supported as a value")
        self.enter("neighbors")
        try:
            key = self.current_key()
            local_t = _as_node_tensor(value, self.batch_size, self.device)
            self._queue_send(key, local_t)
            edge_vals, edge_valid = self._gather_incoming(key, local_t)
            loc_p, edg_p = _promote_pair(local_t, edge_vals)
            return BatchedNeighborhoodField(self.edges, loc_p, edg_p, edge_valid, has_self=True)
        finally:
            self.exit()

    def _exec_exchange(
        self, init: Any
    ) -> tuple[torch.Tensor, BatchedNeighborhoodField, Callable[[Any], torch.Tensor]]:
        self.enter("exchange")
        try:
            key = self.current_key()
            local_t = self._read_or_init_state(key, init)
            self._queue_send(key, local_t)
            edge_vals, edge_valid = self._gather_incoming(key, local_t)
            loc_p, edg_p = _promote_pair(local_t, edge_vals)
            field_obj = BatchedNeighborhoodField(
                self.edges, loc_p, edg_p, edge_valid, has_self=True, default=local_t
            )

            def send_fn(new_value: Any) -> torch.Tensor:
                written = self._write_masked_state(key, new_value)
                self._queue_send(key, written)
                return written

            return local_t, field_obj, send_fn
        finally:
            self.exit()

    def finish_batch(self) -> None:
        """Prune unread branch states for ``batch_ids`` and publish outgoing messages."""
        batch_ids = self.edges.batch_ids
        for key, sslot in self.store.states.items():
            read_mask = self._read_masks.get(key)
            if read_mask is None:
                sslot.valid[batch_ids] = False
            elif not bool(read_mask.all().item()):
                sslot.valid[batch_ids[~read_mask]] = False

        self._commit_batch_outputs(batch_ids)
        if self.store.uses_edge_slots:
            self._publish_edge_slots(batch_ids)
        else:
            self._publish_slots(
                table=self.store.node_outboxes,
                capacity=self.store.topology.num_nodes,
                target_indices=batch_ids,
                arrivals=self.batch_times + self.store.channel.delay,
                pend_at=self.store.node_pending_at,
                comm_at=self.store.node_committed_at,
                batch_idx_of_target=torch.arange(
                    self.batch_size, dtype=torch.int64, device=self.device
                ),
            )

    def _commit_batch_outputs(self, batch_ids: torch.Tensor) -> None:
        ctx: BatchNodeContext = self.node_context  # type: ignore[assignment]
        for out_name, (_buf, out_valid) in self.store.outputs.items():
            if out_name not in ctx.batch_outputs:
                out_valid[batch_ids] = False
        for out_name, (b_buf, b_mask) in ctx.batch_outputs.items():
            existing = self.store.outputs.get(out_name)
            if existing is None:
                g_buf = _alloc_like(b_buf, self.store.topology.num_nodes)
                g_valid = torch.zeros(
                    self.store.topology.num_nodes, dtype=torch.bool, device=self.device
                )
                g_buf[batch_ids[b_mask]] = b_buf[b_mask]
                g_valid[batch_ids[b_mask]] = True
                self.store.outputs[out_name] = (g_buf, g_valid)
            else:
                g_buf, g_valid = existing
                g_buf, b_buf = _promote_pair(g_buf, b_buf)
                g_buf[batch_ids[b_mask]] = b_buf[b_mask]
                g_valid[batch_ids] = b_mask
                self.store.outputs[out_name] = (g_buf, g_valid)

    def _publish_slots(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        *,
        table: dict[int, _OutboxBuffer],
        capacity: int,
        target_indices: torch.Tensor,
        arrivals: torch.Tensor,
        pend_at: torch.Tensor,
        comm_at: torch.Tensor,
        batch_idx_of_target: torch.Tensor,
    ) -> None:
        promote_time = pend_at[target_indices] <= arrivals
        for key, slot in table.items():
            if bool(promote_time.any().item()):
                p_idx = target_indices[promote_time]
                slot.committed_val[p_idx] = slot.pending_val[p_idx]
                slot.committed_valid[p_idx] = slot.pending_valid[p_idx]
            if key not in self._sent:
                slot.pending_valid[target_indices] = False

        if bool(promote_time.any().item()):
            p_idx = target_indices[promote_time]
            comm_at[p_idx] = pend_at[p_idx]
        pend_at[target_indices] = arrivals

        for key, (val_t, sent_mask) in self._sent.items():
            slot = table.get(key)
            if slot is None:
                slot = _OutboxBuffer(
                    _alloc_like(val_t, capacity),
                    torch.zeros(capacity, dtype=torch.bool, device=self.device),
                    _alloc_like(val_t, capacity),
                    torch.zeros(capacity, dtype=torch.bool, device=self.device),
                )
                table[key] = slot
            elif slot.pending_val.dtype != val_t.dtype:
                common = torch.promote_types(slot.pending_val.dtype, val_t.dtype)
                slot.committed_val = slot.committed_val.to(dtype=common)
                slot.pending_val = slot.pending_val.to(dtype=common)
                val_t = val_t.to(dtype=common)
            target_sent = sent_mask[batch_idx_of_target]
            active_targets = target_indices[target_sent]
            slot.pending_val[active_targets] = val_t[batch_idx_of_target[target_sent]]
            slot.pending_valid[target_indices] = target_sent

    def _publish_edge_slots(self, batch_ids: torch.Tensor) -> None:
        topo = self.store.topology
        n_edges = int(topo.sender.numel())
        if n_edges == 0 or self.store.channel.loss >= 1.0:
            return
        assert self.store.edge_pending_at is not None
        assert self.store.edge_committed_at is not None

        lookup = torch.full((topo.num_nodes,), -1, dtype=torch.int64, device=self.device)
        lookup[batch_ids] = torch.arange(self.batch_size, dtype=torch.int64, device=self.device)
        sender_bidx = lookup[topo.sender]
        firing = torch.nonzero(sender_bidx >= 0, as_tuple=False).squeeze(-1)
        if firing.numel() == 0:
            return

        if self.store.channel.loss > 0.0:
            draws = torch.rand(firing.numel(), generator=self._rng, device=self.device)
            firing = firing[draws >= self.store.channel.loss]
            if firing.numel() == 0:
                return

        bidx = sender_bidx[firing]
        arrivals = self.batch_times[bidx] + self.store.channel.delay
        if self.store.channel.jitter > 0.0:
            jitter = torch.rand(
                firing.numel(), generator=self._rng, device=self.device, dtype=torch.float64
            )
            arrivals = arrivals + jitter * self.store.channel.jitter

        self._publish_slots(
            table=self.store.edge_outboxes,
            capacity=n_edges,
            target_indices=firing,
            arrivals=arrivals,
            pend_at=self.store.edge_pending_at,
            comm_at=self.store.edge_committed_at,
            batch_idx_of_target=bidx,
        )

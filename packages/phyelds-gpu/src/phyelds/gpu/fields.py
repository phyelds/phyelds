"""Vectorized counterpart of ``NeighborhoodField`` over ``M`` devices and ``E_B`` edges."""

import math
import operator
from typing import Any, Callable

import torch

from phyelds.gpu.topology import SubbatchEdges

_MISSING = object()


def _as_node_tensor(
    value: Any, batch_size: int, device: torch.device, dtype: torch.dtype | None = None
) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        out = value.to(device=device)
        if dtype is not None:
            out = out.to(dtype=dtype)
        return out.expand(batch_size).clone() if out.ndim == 0 else out
    if value is None:
        target_dtype = torch.int64 if dtype is None else dtype
        fill = math.nan if target_dtype.is_floating_point else -1
        return torch.full((batch_size,), fill, dtype=target_dtype, device=device)
    if isinstance(value, bool):
        target_dtype = torch.bool if dtype is None else dtype
        return torch.full((batch_size,), value, dtype=target_dtype, device=device)
    if isinstance(value, int):
        target_dtype = torch.int64 if dtype is None else dtype
        return torch.full((batch_size,), value, dtype=target_dtype, device=device)
    target_dtype = torch.float64 if dtype is None else dtype
    return torch.full((batch_size,), float(value), dtype=target_dtype, device=device)


def _promote_pair(left: torch.Tensor, right: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    common = torch.promote_types(left.dtype, right.dtype)
    return left.to(dtype=common), right.to(dtype=common)


def _min_sentinel(dtype: torch.dtype) -> float | int | bool:
    if dtype == torch.bool:
        return True
    return float("inf") if dtype.is_floating_point else torch.iinfo(dtype).max


def _max_sentinel(dtype: torch.dtype) -> float | int | bool:
    if dtype == torch.bool:
        return False
    return float("-inf") if dtype.is_floating_point else torch.iinfo(dtype).min


_KNOWN_OPS: dict[Any, str] = {
    operator.add: "sum",
    sum: "sum",
    operator.mul: "prod",
    max: "amax",
    min: "amin",
    operator.or_: "or",
    operator.and_: "and",
}


def _probe_callable_op(accumulator: Callable[[Any, Any], Any]) -> str | None:
    try:
        if accumulator(2.0, 3.0) == 5.0 and accumulator(5.0, 0.0) == 5.0:
            return "sum"
        if accumulator(2.0, 3.0) == 6.0 and accumulator(5.0, 1.0) == 5.0:
            return "prod"
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        if (
            accumulator(False, False) is False
            and accumulator(False, True) is True
            and accumulator(True, False) is True
        ):
            return "or"
        if (
            accumulator(True, True) is True
            and accumulator(True, False) is False
            and accumulator(False, True) is False
        ):
            return "and"
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return None


def _identify_binary_op(accumulator: Callable[[Any, Any], Any]) -> str | None:
    direct = _KNOWN_OPS.get(accumulator)
    if direct is not None:
        return direct
    tagged = getattr(accumulator, "_gpu_kind", None)
    if tagged in ("max", "min"):
        return "amax" if tagged == "max" else "amin"
    return _probe_callable_op(accumulator)


class BatchedNeighborhoodField:  # pylint: disable=too-many-public-methods,too-many-instance-attributes
    """
    Neighborhood field across ``M`` concurrent devices, backed by PyTorch edge & node tensors.

    Implements the same algebra and reduction methods as ``phyelds.data.NeighborhoodField`` so
    standard ``@aggregate`` programs run unchanged on CPU SIMD or CUDA GPUs.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        edges: SubbatchEdges,
        local_val: torch.Tensor,
        edge_val: torch.Tensor,
        edge_valid: torch.Tensor,
        *,
        has_self: bool = True,
        default: Any = _MISSING,
    ) -> None:
        self.edges = edges
        self.local_val = local_val
        self.edge_val = edge_val
        self.edge_valid = edge_valid
        self.has_self = has_self
        self.default = local_val if default is _MISSING else default

    @property
    def device(self) -> torch.device:
        """Torch device hosting this field."""
        return self.edges.batch_ids.device

    @property
    def batch_size(self) -> int:
        """Number of active devices represented by this batched field."""
        return self.edges.batch_size

    def count_entries(self, *, include_self: bool = True) -> torch.Tensor:
        """Number of valid entries per device (`int64 [M]`)."""
        counts = torch.zeros(self.batch_size, dtype=torch.int64, device=self.device)
        if self.edge_valid.numel() > 0:
            counts.scatter_add_(0, self.edges.local_receiver, self.edge_valid.to(torch.int64))
        if include_self and self.has_self:
            counts = counts + 1
        return counts

    def local(self) -> torch.Tensor | None:
        """Return the local value tensor (`[M, ...]`), or ``None`` when self was excluded."""
        return self.local_val if self.has_self else None

    def without_self(self) -> "BatchedNeighborhoodField":
        """Return a view of this field excluding each device's own entry."""
        return BatchedNeighborhoodField(
            self.edges,
            self.local_val,
            self.edge_val,
            self.edge_valid,
            has_self=False,
            default=self.default,
        )

    def _with_local(self, value: Any) -> "BatchedNeighborhoodField":
        new_local = _as_node_tensor(value, self.batch_size, self.device)
        local_p, edge_p = _promote_pair(new_local, self.edge_val)
        return BatchedNeighborhoodField(
            self.edges, local_p, edge_p, self.edge_valid, has_self=True, default=self.default
        )

    def _distances_to(self, origin: Any) -> "BatchedNeighborhoodField":
        raw_orig = (
            origin
            if isinstance(origin, torch.Tensor)
            else torch.as_tensor(origin, device=self.device)
        )
        orig = raw_orig.to(device=self.device, dtype=torch.float64)
        local_d = torch.linalg.vector_norm(self.local_val.to(torch.float64) - orig, dim=-1)
        if self.edge_val.numel() == 0:
            edge_d = torch.zeros(0, dtype=torch.float64, device=self.device)
        else:
            rcv_orig = orig[self.edges.local_receiver]
            edge_d = torch.linalg.vector_norm(self.edge_val.to(torch.float64) - rcv_orig, dim=-1)
        return BatchedNeighborhoodField(
            self.edges, local_d, edge_d, self.edge_valid, has_self=self.has_self
        )

    def map(self, func: Callable[[Any], Any]) -> "BatchedNeighborhoodField":
        """Apply a tensor-compatible function ``func`` across local and edge values."""
        new_local = func(self.local_val)
        new_edge = func(self.edge_val) if self.edge_val.numel() > 0 else new_local[:0]
        mapped_def = None if self.default is None else func(self.default)
        return BatchedNeighborhoodField(
            self.edges,
            new_local,
            new_edge,
            self.edge_valid,
            has_self=self.has_self,
            default=mapped_def,
        )

    def coerce_in(self, lower: Any, upper: Any) -> "BatchedNeighborhoodField":
        """Clamp every value in the field to ``[lower, upper]``."""
        if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower > upper:
            raise ValueError(f"lower bound ({lower}) must not exceed upper bound ({upper})")
        return self.map(lambda tensor: torch.clamp(tensor, min=lower, max=upper))

    def replace_matching(
        self, replacement: Any, predicate: Callable[[Any], Any]
    ) -> "BatchedNeighborhoodField":
        """Replace values satisfying ``predicate`` with ``replacement``."""
        return self.map(lambda tensor: torch.where(predicate(tensor), replacement, tensor))

    def _reduce_edges(
        self,
        *,
        mode: str,
        include_self: bool,
        default: Any = None,
    ) -> torch.Tensor:
        use_self = include_self and self.has_self
        val_dtype = self.local_val.dtype
        work_dtype = torch.int64 if val_dtype == torch.bool else val_dtype

        if mode == "amin":
            ident = 1 if val_dtype == torch.bool else _min_sentinel(work_dtype)
        elif mode == "amax":
            ident = 0 if val_dtype == torch.bool else _max_sentinel(work_dtype)
        elif mode == "sum":
            ident = 0
        else:
            ident = 1

        if use_self:
            out = self.local_val.to(dtype=work_dtype).clone()
        else:
            out = torch.full((self.batch_size,), ident, dtype=work_dtype, device=self.device)

        if self.edge_val.numel() > 0:
            edge_work = self.edge_val.to(dtype=work_dtype)
            safe_edge = torch.where(
                self.edge_valid,
                edge_work,
                torch.full_like(edge_work, ident),
            )
            out.scatter_reduce_(
                0, self.edges.local_receiver, safe_edge, reduce=mode, include_self=True
            )

        if val_dtype == torch.bool and mode in ("amin", "amax"):
            out = out.to(dtype=torch.bool)

        if not use_self and default is not None:
            has_any = self.count_entries(include_self=False) > 0
            def_tensor = _as_node_tensor(default, self.batch_size, self.device)
            out, def_tensor = _promote_pair(out, def_tensor)
            out = torch.where(has_any, out, def_tensor)
        return out

    def min(
        self,
        *,
        include_self: bool = True,
        default: Any = None,
        key: Callable[[Any], Any] | None = None,
    ) -> torch.Tensor:
        """Return per-device minimum value (`[M]`)."""
        if key is not None:
            raise NotImplementedError("custom key functions are not supported on GPU fields")
        return self._reduce_edges(mode="amin", include_self=include_self, default=default)

    def max(
        self,
        *,
        include_self: bool = True,
        default: Any = None,
        key: Callable[[Any], Any] | None = None,
    ) -> torch.Tensor:
        """Return per-device maximum value (`[M]`)."""
        if key is not None:
            raise NotImplementedError("custom key functions are not supported on GPU fields")
        return self._reduce_edges(mode="amax", include_self=include_self, default=default)

    def sum(self, *, include_self: bool = True, start: Any = 0) -> torch.Tensor:
        """Return per-device sum of values (`[M]`)."""
        base = self._reduce_edges(mode="sum", include_self=include_self, default=0)
        if isinstance(start, (int, float)) and start == 0:
            return base
        start_t = _as_node_tensor(start, self.batch_size, self.device)
        base, start_t = _promote_pair(base, start_t)
        return base + start_t

    def product(self, *, include_self: bool = True, start: Any = 1) -> torch.Tensor:
        """Return per-device product of values (`[M]`)."""
        base = self._reduce_edges(mode="prod", include_self=include_self, default=1)
        if isinstance(start, (int, float)) and start == 1:
            return base
        start_t = _as_node_tensor(start, self.batch_size, self.device)
        base, start_t = _promote_pair(base, start_t)
        return base * start_t

    def any(
        self,
        predicate: Callable[[Any], Any] | None = None,
        *,
        include_self: bool = True,
    ) -> torch.Tensor:
        """Check per-device whether any neighbor value is truthy (or matches ``predicate``)."""
        target = self if predicate is None else self.map(predicate)
        as_bool = target.map(lambda t: t.to(dtype=torch.bool))
        return as_bool._reduce_edges(  # pylint: disable=protected-access
            mode="amax", include_self=include_self, default=False
        )

    def all(
        self,
        predicate: Callable[[Any], Any] | None = None,
        *,
        include_self: bool = True,
    ) -> torch.Tensor:
        """Check per-device whether all neighbor values are truthy (or match ``predicate``)."""
        target = self if predicate is None else self.map(predicate)
        as_bool = target.map(lambda t: t.to(dtype=torch.bool))
        return as_bool._reduce_edges(  # pylint: disable=protected-access
            mode="amin", include_self=include_self, default=True
        )

    def none(
        self,
        predicate: Callable[[Any], Any] | None = None,
        *,
        include_self: bool = True,
    ) -> torch.Tensor:
        """Check per-device that no neighbor value satisfies ``predicate``."""
        return ~self.any(predicate, include_self=include_self)

    def count_matching(
        self, predicate: Callable[[Any], Any], *, include_self: bool = True
    ) -> torch.Tensor:
        """Count per-device how many entries satisfy ``predicate``."""
        indicators = self.map(lambda t: predicate(t).to(dtype=torch.int64))
        return indicators.sum(include_self=include_self)

    def _id_of_extremum(self, best_val: torch.Tensor, *, include_self: bool) -> torch.Tensor:
        max_id = torch.iinfo(torch.int64).max
        if include_self and self.has_self:
            winners = torch.where(
                self.local_val == best_val,
                self.edges.batch_ids,
                torch.full_like(self.edges.batch_ids, max_id),
            )
        else:
            winners = torch.full((self.batch_size,), max_id, dtype=torch.int64, device=self.device)
        if self.edge_val.numel() > 0:
            edge_match = self.edge_valid & (self.edge_val == best_val[self.edges.local_receiver])
            cand_ids = torch.where(
                edge_match,
                self.edges.global_sender,
                torch.full_like(self.edges.global_sender, max_id),
            )
            winners.scatter_reduce_(
                0, self.edges.local_receiver, cand_ids, reduce="amin", include_self=True
            )
        return torch.where(winners == max_id, torch.full_like(winners, -1), winners)

    def id_of_min(
        self, *, include_self: bool = True, key: Callable[[Any, Any], Any] | None = None
    ) -> torch.Tensor:
        """Return per-device winning node ID of the minimal value (ties prefer smallest ID)."""
        if key is not None:
            raise NotImplementedError("custom key functions are not supported on GPU fields")
        return self._id_of_extremum(
            self.min(include_self=include_self, default=float("inf")), include_self=include_self
        )

    def id_of_max(
        self, *, include_self: bool = True, key: Callable[[Any, Any], Any] | None = None
    ) -> torch.Tensor:
        """Return per-device winning node ID of the maximal value (ties prefer smallest ID)."""
        if key is not None:
            raise NotImplementedError("custom key functions are not supported on GPU fields")
        return self._id_of_extremum(
            self.max(include_self=include_self, default=float("-inf")), include_self=include_self
        )

    def fold(
        self,
        initial: Any,
        accumulator: Callable[[Any, Any], Any],
        *,
        include_self: bool = True,
    ) -> torch.Tensor:
        """Fold field entries per device using recognized associative vector operations."""
        kind = _identify_binary_op(accumulator)
        init_t = _as_node_tensor(initial, self.batch_size, self.device)
        if kind == "sum":
            return self.sum(include_self=include_self, start=init_t)
        if kind == "prod":
            return self.product(include_self=include_self, start=init_t)
        if kind == "amax":
            a, b = _promote_pair(init_t, self.max(include_self=include_self, default=init_t))
            return torch.maximum(a, b)
        if kind == "amin":
            a, b = _promote_pair(init_t, self.min(include_self=include_self, default=init_t))
            return torch.minimum(a, b)
        if kind == "or":
            return init_t.to(torch.bool) | self.any(include_self=include_self)
        if kind == "and":
            return init_t.to(torch.bool) & self.all(include_self=include_self)
        raise TypeError("GPU BatchedNeighborhoodField.fold requires +, *, min, max, and, or")

    def _fold_where_equal(
        self,
        keys_field: "BatchedNeighborhoodField",
        expected: Any,
        initial: Any,
        accumulator: Callable[[Any, Any], Any],
    ) -> torch.Tensor:
        exp_t = _as_node_tensor(expected, self.batch_size, self.device, dtype=torch.int64)
        local_match = self.has_self & keys_field.has_self & (keys_field.local_val == exp_t)
        if self.edge_val.numel() > 0:
            edge_match = (
                self.edge_valid
                & keys_field.edge_valid
                & (keys_field.edge_val == exp_t[self.edges.local_receiver])
            )
        else:
            edge_match = self.edge_valid
        masked_peers = BatchedNeighborhoodField(
            self.edges,
            self.local_val,
            self.edge_val,
            edge_match,
            has_self=False,
            default=self.default,
        )
        folded = masked_peers.fold(initial, accumulator, include_self=False)
        if bool(local_match.any().item()):
            with_self = accumulator(folded, self.local_val)
            folded, with_self = _promote_pair(folded, with_self)
            folded = torch.where(local_match, with_self, folded)
        return folded

    def _reduce_all(self, initial: Any, callback: Callable[..., Any]) -> torch.Tensor:
        init_t = _as_node_tensor(initial, self.batch_size, self.device)
        kind = getattr(callback, "_gpu_kind", None)
        if callback is max or kind == "max":
            a, b = _promote_pair(init_t, self.max(include_self=True, default=init_t))
            return torch.maximum(a, b)
        if callback is min or kind == "min":
            a, b = _promote_pair(init_t, self.min(include_self=True, default=init_t))
            return torch.minimum(a, b)
        raise TypeError("GPU gossip supports max and min reductions")

    def _binary_op(
        self, other: Any, op: Callable[[torch.Tensor, torch.Tensor], torch.Tensor]
    ) -> "BatchedNeighborhoodField":
        if isinstance(other, BatchedNeighborhoodField):
            loc_a, loc_b = _promote_pair(self.local_val, other.local_val)
            edg_a, edg_b = _promote_pair(self.edge_val, other.edge_val)
            return BatchedNeighborhoodField(
                self.edges,
                op(loc_a, loc_b),
                op(edg_a, edg_b) if edg_a.numel() > 0 else op(loc_a[:0], loc_b[:0]),
                self.edge_valid & other.edge_valid,
                has_self=self.has_self and other.has_self,
            )
        rhs = _as_node_tensor(other, self.batch_size, self.device)
        loc_a, loc_b = _promote_pair(self.local_val, rhs)
        new_loc = op(loc_a, loc_b)
        if self.edge_val.numel() > 0:
            edg_a, edg_b = _promote_pair(self.edge_val, rhs[self.edges.local_receiver])
            new_edg = op(edg_a, edg_b)
        else:
            new_edg = new_loc[:0]
        return BatchedNeighborhoodField(
            self.edges, new_loc, new_edg, self.edge_valid, has_self=self.has_self
        )

    def __add__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.add)

    def __radd__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, lambda a, b: torch.add(b, a))

    def __sub__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.sub)

    def __mul__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.mul)

    def __truediv__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.true_divide)

    def __floordiv__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, lambda a, b: torch.div(a, b, rounding_mode="floor"))

    def __mod__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.remainder)

    def __pow__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.pow)

    def __and__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.bitwise_and)

    def __or__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.bitwise_or)

    def __xor__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.bitwise_xor)

    def __invert__(self) -> "BatchedNeighborhoodField":
        return self.map(torch.bitwise_not)

    def __lt__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.lt)

    def __le__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.le)

    def __gt__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.gt)

    def __ge__(self, other: Any) -> "BatchedNeighborhoodField":
        return self._binary_op(other, torch.ge)

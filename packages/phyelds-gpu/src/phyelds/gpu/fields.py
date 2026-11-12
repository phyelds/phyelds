"""
The neighborhood field of a batch of devices: a value of each device's own, and one on each
edge into it, the value its sender sent.
"""
import math
import operator
from collections.abc import Callable
from typing import Any

import torch

from phyelds.gpu.tensors import as_rows, as_tensor, common, where_rows
from phyelds.gpu.topology import BatchEdges

# The reductions a fold can run on a batch, told by the accumulator itself.
_FOLDS: dict[Any, str] = {
    operator.add: "sum",
    operator.mul: "prod",
    max: "amax",
    min: "amin",
    operator.or_: "any",
    operator.and_: "all",
}
_COMBINE: dict[str, Callable[[torch.Tensor, torch.Tensor], torch.Tensor]] = {
    "sum": torch.add,
    "prod": torch.mul,
    "amax": torch.maximum,
    "amin": torch.minimum,
}


class BatchField:  # pylint: disable=too-many-public-methods  # the API of a field
    """
    The ``NeighborhoodField`` of every device of a batch at once.

    It runs the operations of ``NeighborhoodField`` for all the devices together. A callback,
    given to ``map``, ``any`` or ``count_matching``, receives tensors with one row per entry,
    so it must compute elementwise, as ``operator.eq`` or ``lambda value: value + 1`` do; the
    values of the device go to ``map`` as its ``values``, not in a closure.

    Args:
        edges: The edges into the devices of the batch.
        local: The value of each device (``[M, ...]``), or one for all.
        values: The value on each edge (``[E, ...]``), or one for all.
        present: Which edges carry a value (``bool [E]``); all of them by default.
        local_present: Which devices hold a value of their own (``bool [M]``); all of them by
            default.
        default: The value of the field for the devices it does not hold: one per device, one
            for all, or ``None``.
    """

    __slots__ = ("edges", "local_values", "values", "present", "local_present", "default")

    def __init__(  # pylint: disable=too-many-arguments
        self,
        edges: BatchEdges,
        local: Any,
        values: Any,
        present: torch.Tensor | None = None,
        *,
        local_present: torch.Tensor | None = None,
        default: Any = None,
    ):
        device = edges.devices.device
        count = int(edges.senders.numel())
        self.edges = edges
        self.local_values = as_rows(local, edges.num_devices, device)
        """The value of each device (``[M, ...]``), also where it holds none."""
        self.values = as_rows(values, count, device)
        """The value on each edge (``[E, ...]``), also where it carries none."""
        self.present = (
            torch.ones(count, dtype=torch.bool, device=device) if present is None else present
        )
        self.local_present = (
            torch.ones(edges.num_devices, dtype=torch.bool, device=device)
            if local_present is None else local_present
        )
        self.default = default

    def __repr__(self) -> str:
        return f"BatchField(local={self.local_values!r}, values={self.values!r})"

    def __iter__(self):
        raise TypeError("a field of a batch of devices cannot be iterated: reduce it")

    def local(self) -> torch.Tensor:
        """The value of each device, NaN for the devices that hold none."""
        if bool(self.local_present.all()):
            return self.local_values
        nothing = as_rows(None, self._rows, self._device)
        return where_rows(self.local_present, self.local_values, nothing)

    def without_self(self) -> "BatchField":
        """The field without the value of each device."""
        return self._with(local_present=torch.zeros_like(self.local_present))

    def with_local(self, value: Any) -> "BatchField":
        """The field where each device holds ``value``, one per device or one for all."""
        return self._with(
            local=as_rows(value, self._rows, self._device),
            local_present=torch.ones_like(self.local_present),
        )

    def where(self, mask: "BatchField") -> "BatchField":
        """The field restricted to the entries whose value in ``mask`` holds."""
        self.check_edges(mask)
        return self._with(
            present=self.present & mask.present & mask.values.to(torch.bool),
            local_present=(
                self.local_present & mask.local_present & mask.local_values.to(torch.bool)
            ),
        )

    def map(self, func: Callable[..., Any], *values: Any) -> "BatchField":
        """
        Apply ``func`` to every value of the field, and to the default if any.

        Args:
            func: An elementwise function of a tensor of values and of ``values``.
            *values: Values of the devices, each given to the edges into its device.

        Returns:
            The mapped field.
        """
        return BatchField(
            self.edges,
            func(self.local_values, *map(self._on_devices, values)),
            func(self.values, *map(self._on_edges, values)),
            self.present,
            local_present=self.local_present,
            default=None if self.default is None else func(
                as_tensor(self.default, self._device), *values
            ),
        )

    def coerce_in(self, lower: Any, upper: Any) -> "BatchField":
        """
        The field with every value clamped to ``[lower, upper]``.

        Raises:
            ValueError: If ``lower > upper``.
        """
        if lower > upper:
            raise ValueError(f"lower bound ({lower}) must not exceed upper bound ({upper})")
        return self.map(torch.clamp, lower, upper)

    def sum(self, *, include_self: bool = True, start: Any = 0) -> torch.Tensor:
        """The sum of the values of each device, from ``start``."""
        return self.fold(start, operator.add, include_self=include_self)

    def product(self, *, include_self: bool = True, start: Any = 1) -> torch.Tensor:
        """The product of the values of each device, from ``start``."""
        return self.fold(start, operator.mul, include_self=include_self)

    def min(self, *, include_self: bool = True, default: Any = None, key: Any = None):
        """The least value of each device, or ``default`` (NaN for ``None``) if it has none."""
        return self._extreme("amin", include_self, default, key)

    def max(self, *, include_self: bool = True, default: Any = None, key: Any = None):
        """The greatest value of each device, or ``default`` (NaN for ``None``) if it has none."""
        return self._extreme("amax", include_self, default, key)

    def id_of_min(self, *, include_self: bool = True, key: Any = None) -> torch.Tensor:
        """The id of the least value of each device, the least on ties; NaN if it has none."""
        return self._id_of("amin", include_self, key)

    def id_of_max(self, *, include_self: bool = True, key: Any = None) -> torch.Tensor:
        """The id of the greatest value of each device, the least on ties; NaN if it has none."""
        return self._id_of("amax", include_self, key)

    def fold(
        self, initial: Any, accumulator: Callable[[Any, Any], Any], *, include_self: bool = True
    ) -> torch.Tensor:
        """
        Fold the values of each device into one, from ``initial``.

        Args:
            initial: The value to start from: one per device, or one for all.
            accumulator: ``operator.add``, ``operator.mul``, ``max``, ``min``, or, on
                booleans, ``operator.or_`` and ``operator.and_``.
            include_self: Whether to include the value of each device.

        Returns:
            The folded value of each device.

        Raises:
            TypeError: If ``accumulator`` is another function: a batch engine cannot run it
                on the entries one by one.
        """
        reduction = _FOLDS.get(accumulator)
        if reduction is None:
            raise TypeError(
                "a batch engine folds with operator.add, operator.mul, max, min, "
                f"operator.or_ and operator.and_, not {accumulator!r}"
            )
        start = as_rows(initial, self._rows, self._device)
        if reduction == "any":
            return start.to(torch.bool) | self.any(include_self=include_self)
        if reduction == "all":
            return start.to(torch.bool) & self.all(include_self=include_self)
        reduced, _ = self._reduce(reduction, include_self)
        start, reduced = common(start, reduced)
        return _COMBINE[reduction](start, reduced)

    def reduce(
        self, reducer: Callable[[Any, Any], Any], *, include_self: bool = True,
        default: Any = None,
    ) -> torch.Tensor:
        """The values of each device reduced with ``reducer``, or ``default`` if it has none."""
        reduction = _FOLDS.get(reducer)
        if reduction not in _COMBINE:
            raise TypeError(f"a batch engine reduces with operator.add, operator.mul, max and "
                            f"min, not {reducer!r}")
        reduced, found = self._reduce(reduction, include_self)
        return where_rows(found, reduced, as_rows(default, self._rows, self._device))

    def any(self, predicate: Callable[[Any], Any] | None = None, *, include_self: bool = True):
        """Whether any value of each device satisfies ``predicate``, or is truthy."""
        reduced, _ = self._reduce("amax", include_self, *self._truths(predicate))
        return reduced > 0  # a device without entries keeps the identity of amax, negative

    def all(self, predicate: Callable[[Any], Any] | None = None, *, include_self: bool = True):
        """Whether every value of each device satisfies ``predicate``, or is truthy."""
        reduced, _ = self._reduce("amin", include_self, *self._truths(predicate))
        return reduced > 0  # a device without entries keeps the identity of amin, positive

    def none(self, predicate: Callable[[Any], Any] | None = None, *, include_self: bool = True):
        """Whether no value of each device satisfies ``predicate``, or is truthy."""
        return ~self.any(predicate, include_self=include_self)

    def count_matching(self, predicate: Callable[[Any], Any], *, include_self: bool = True):
        """How many values of each device satisfy ``predicate``."""
        counted, _ = self._reduce("sum", include_self, *self._truths(predicate))
        return counted

    # Elementwise operators, as those of NeighborhoodField; a value of each device goes to
    # the edges into it.
    def __add__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.add)

    def __sub__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.sub)

    def __mul__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.mul)

    def __truediv__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.truediv)

    def __floordiv__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.floordiv)

    def __mod__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.mod)

    def __pow__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.pow)

    def __and__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.and_)

    def __or__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.or_)

    def __xor__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.xor)

    def __lt__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.lt)

    def __le__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.le)

    def __gt__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.gt)

    def __ge__(self, other: Any) -> "BatchField":
        return self._binary(other, operator.ge)

    def __invert__(self) -> "BatchField":
        return self.map(operator.invert)

    @staticmethod
    def merged(mask: torch.Tensor, chosen: "BatchField", other: "BatchField") -> "BatchField":
        """The field of ``chosen`` for the devices of ``mask``, of ``other`` for the rest."""
        chosen.check_edges(other)
        on_edges = mask[chosen.edges.receivers]
        rows, device = chosen.edges.num_devices, mask.device
        defaults = (chosen.default, other.default)
        return BatchField(
            chosen.edges,
            where_rows(mask, chosen.local_values, other.local_values),
            where_rows(on_edges, chosen.values, other.values),
            torch.where(on_edges, chosen.present, other.present),
            local_present=torch.where(mask, chosen.local_present, other.local_present),
            default=None if None in defaults else where_rows(
                mask, *(as_rows(value, rows, device) for value in defaults)
            ),
        )

    @property
    def _rows(self) -> int:
        return self.edges.num_devices

    @property
    def _device(self) -> torch.device:
        return self.edges.devices.device

    def _with(self, **changes: Any) -> "BatchField":
        """A copy of the field with ``changes`` to its local value or to its entries."""
        return BatchField(
            self.edges,
            changes.get("local", self.local_values),
            self.values,
            changes.get("present", self.present),
            local_present=changes.get("local_present", self.local_present),
            default=self.default,
        )

    def check_edges(self, other: "BatchField") -> None:
        """
        Check that ``other`` belongs to the same batch of devices.

        Raises:
            ValueError: If it does not.
        """
        if other.edges is not self.edges:
            raise ValueError("the fields belong to different batches of devices")

    def _on_edges(self, value: Any) -> Any:
        """A value of the devices as one on each edge into them: tensors are gathered."""
        if isinstance(value, BatchField):
            return value.values
        if isinstance(value, torch.Tensor) and value.ndim > 0:
            return value[self.edges.receivers]
        return value

    @staticmethod
    def _on_devices(value: Any) -> Any:
        """A value of the devices as one of each device: a field gives its local values."""
        return value.local_values if isinstance(value, BatchField) else value

    def _binary(self, other: Any, op: Callable[[Any, Any], Any]) -> "BatchField":
        """``op`` of each entry and ``other``: a field, a value of each device, or one for all."""
        if not isinstance(other, BatchField):
            return self.map(op, other)
        self.check_edges(other)
        defaults = (self.default, other.default)
        return BatchField(
            self.edges,
            op(self.local_values, other.local_values),
            op(self.values, other.values),
            self.present & other.present,
            local_present=self.local_present & other.local_present,
            default=None if None in defaults else op(*defaults),
        )

    def _truths(self, predicate: Callable[[Any], Any] | None) -> tuple[torch.Tensor, ...]:
        """The truth of ``predicate``, or of the values, of each device and edge, as 0 or 1."""
        mapped = self if predicate is None else self.map(predicate)
        return tuple(
            as_tensor(values, self._device).to(torch.bool).to(torch.int64)
            for values in (mapped.local_values, mapped.values)
        )

    def _reduce(
        self, reduction: str, include_self: bool,
        local: torch.Tensor | None = None, values: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        The ``reduction`` (``sum``, ``prod``, ``amax`` or ``amin``) of the entries of each
        device, and whether it has any; of ``local`` and ``values`` instead of those of the
        field, if given.
        """
        local, values = common(
            self.local_values if local is None else local,
            self.values if values is None else values,
        )
        if values.dtype == torch.bool:
            local, values = local.to(torch.int64), values.to(torch.int64)
        receivers = self.edges.receivers[self.present]
        entries = values[self.present]
        reduced = torch.full(
            (self._rows, *values.shape[1:]), _identity(reduction, values.dtype),
            dtype=values.dtype, device=self._device,
        )
        index = receivers.view(-1, *[1] * (entries.ndim - 1)).expand_as(entries)
        reduced.scatter_reduce_(0, index, entries, reduce=reduction, include_self=True)
        found = torch.zeros(self._rows, dtype=torch.bool, device=self._device)
        found[receivers] = True
        if include_self:
            reduced = where_rows(
                self.local_present, _COMBINE[reduction](reduced, local), reduced
            )
            found = found | self.local_present
        return reduced, found

    def _extreme(self, reduction: str, include_self: bool, default: Any, key: Any):
        if key is not None:
            raise TypeError("a batch engine compares the values themselves, without a key")
        reduced, found = self._reduce(reduction, include_self)
        return where_rows(found, reduced, as_rows(default, self._rows, self._device))

    def _id_of(self, reduction: str, include_self: bool, key: Any) -> torch.Tensor:
        best = self._extreme(reduction, include_self, None, key)
        local, values = common(self.local_values, self.values)
        receivers = self.edges.receivers
        winners = self.present & (values == best[receivers])
        unset = torch.iinfo(torch.int64).max
        ids = torch.full((self._rows,), unset, dtype=torch.int64, device=self._device)
        ids.scatter_reduce_(0, receivers[winners], self.edges.senders[winners],
                            reduce="amin", include_self=True)
        if include_self:
            own = self.local_present & (local == best)
            ids = torch.where(own, torch.minimum(ids, self.edges.devices), ids)
        if bool((ids != unset).all()):
            return ids
        return torch.where(ids != unset, ids.to(torch.float64), math.nan)


def _identity(reduction: str, dtype: torch.dtype) -> float | int:
    """The value that ``reduction`` leaves unchanged: what a device without entries gets."""
    if reduction == "sum":
        return 0
    if reduction == "prod":
        return 1
    if dtype.is_floating_point:
        return math.inf if reduction == "amin" else -math.inf
    limits = torch.iinfo(dtype)
    return limits.max if reduction == "amin" else limits.min

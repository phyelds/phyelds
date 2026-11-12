"""
The values of a batch of devices as tensors, with one row per device.

On a batch engine ``None`` is NaN: the devices for which a branch returns nothing get NaN,
which, as ``None``, equals nothing.
"""
import math
from typing import Any

import torch


def as_rows(value: Any, rows: int, device: torch.device) -> torch.Tensor:
    """
    ``value`` with one row per device.

    Args:
        value: A tensor with ``rows`` rows, kept as it is; or a value for every device: a
            number, ``None``, a 0-dimensional tensor, or a tuple of numbers.
        rows: How many devices the rows are for.
        device: The torch device of the result.

    Returns:
        A tensor whose first dimension is ``rows``.

    Raises:
        TypeError: If ``value`` is not a number, ``None``, a tuple of numbers or a tensor.
        ValueError: If ``value`` is a tensor with another number of rows.
    """
    if isinstance(value, torch.Tensor):
        tensor = value.to(device)
        if tensor.ndim == 0:
            return tensor.expand(rows)
        if tensor.shape[0] != rows:
            raise ValueError(f"a value of {rows} devices needs {rows} rows, not {tensor.shape[0]}")
        return tensor
    if value is None:
        return torch.full((rows,), math.nan, dtype=torch.float64, device=device)
    try:
        tensor = torch.as_tensor(value, dtype=_dtype(value), device=device)
    except (TypeError, ValueError, RuntimeError) as error:
        raise TypeError(
            "a batch engine holds numbers, tuples of numbers and tensors, "
            f"not {type(value).__name__}"
        ) from error
    return tensor.expand(rows, *tensor.shape)


def as_tensor(value: Any, device: torch.device) -> torch.Tensor:
    """``value`` as a tensor, with 64 bits for Python numbers: a tensor stays as it is."""
    if isinstance(value, torch.Tensor):
        return value.to(device)
    return torch.as_tensor(value, dtype=_dtype(value), device=device)


def where_rows(mask: torch.Tensor, chosen: torch.Tensor, other: torch.Tensor) -> torch.Tensor:
    """The rows of ``chosen`` where ``mask`` holds, those of ``other`` elsewhere."""
    chosen, other = common(chosen, other)
    return torch.where(mask.view(-1, *[1] * (chosen.ndim - 1)), chosen, other)


def common(*tensors: torch.Tensor) -> tuple[torch.Tensor, ...]:
    """``tensors`` converted to the type that holds the values of all of them."""
    dtype = tensors[0].dtype
    for tensor in tensors[1:]:
        dtype = torch.promote_types(dtype, tensor.dtype)
    return tuple(tensor.to(dtype) for tensor in tensors)


def _dtype(value: Any) -> torch.dtype | None:
    """The type of a tensor holding ``value``: 64 bits for numbers, as Python has."""
    if isinstance(value, bool):
        return torch.bool
    if isinstance(value, int):
        return torch.int64
    if isinstance(value, float):
        return torch.float64
    return torch.float64 if any(isinstance(item, float) for item in value) else None

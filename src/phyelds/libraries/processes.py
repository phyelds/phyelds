"""
Aggregate processes library (ScaFi-style ``spawn`` / ``sspawn``).

Allows spawning dynamic, spatially and temporally scoped aggregate computations
identified by keys, with full lifecycle management (``OUTPUT``, ``BUBBLE``,
``EXTERNAL``, ``TERMINATED``).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
import inspect
from typing import Any, Generic, TypeVar

from phyelds import engine
from phyelds.calculus import aggregate, exchange
from phyelds.data import NeighborhoodField

K = TypeVar("K")
A = TypeVar("A")
R = TypeVar("R")


class ProcessStatus(Enum):
    """Lifecycle status returned by an aggregate process on the local device."""

    OUTPUT = "output"
    BUBBLE = "bubble"
    EXTERNAL = "external"
    TERMINATED = "terminated"


OUTPUT = ProcessStatus.OUTPUT
BUBBLE = ProcessStatus.BUBBLE
EXTERNAL = ProcessStatus.EXTERNAL
TERMINATED = ProcessStatus.TERMINATED


@dataclass(frozen=True)
class ProcessOutput(Generic[R]):
    """
    Result and lifecycle status returned by a spawned process instance.

    Attributes:
        value: Local output value computed by the process.
        status: Either a ``ProcessStatus`` or a ``bool`` (``True`` -> ``OUTPUT``,
            ``False`` -> ``EXTERNAL``).
    """

    value: R
    status: ProcessStatus | bool = ProcessStatus.OUTPUT

    def normalized_status(self) -> ProcessStatus:
        """Convert boolean shorthand into a ``ProcessStatus``."""
        if isinstance(self.status, bool):
            return ProcessStatus.OUTPUT if self.status else ProcessStatus.EXTERNAL
        return self.status


class _ProcessTransaction:
    """Isolate the alignment path and state/message side effects of one process key."""

    def __init__(self, key: Any) -> None:
        self.key = key
        self.committed = False
        self._engine = engine.get()
        self._saved_to_send: dict[str, Any] = {}
        self._saved_state_trace: dict[str, Any] = {}
        self._saved_reads: set[str] = set()

    def __enter__(self) -> "_ProcessTransaction":
        state = self._engine.engine_state
        self._saved_to_send = state.to_send.copy()
        self._saved_state_trace = state.state_trace.copy()
        self._saved_reads = state.reads.copy()
        state.stack.append(f"process:{self.key!r}")
        state.count_stack.append(0)
        return self

    def commit(self) -> None:
        """Commit state updates and outgoing messages produced by the process."""
        self.committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        state = self._engine.engine_state
        if state.stack:
            state.stack.pop()
            state.count_stack.pop()
        if not self.committed:
            state.to_send = self._saved_to_send
            state.state_trace = self._saved_state_trace
            state.reads = self._saved_reads


def _invoke_process(
    process: Callable[..., Any],
    key: K,
    args: A,
) -> ProcessOutput[Any]:
    """Call ``process`` with ``(key)`` or ``(key, args)`` and normalize its output."""
    try:
        params = list(inspect.signature(process).parameters.values())
        positional_kinds = (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        positional = [p for p in params if p.kind in positional_kinds]
        takes_one = len(positional) == 1 and not any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
        )
    except (TypeError, ValueError):
        takes_one = False

    raw = process(key) if takes_one else process(key, args)
    if isinstance(raw, ProcessOutput):
        return raw
    if isinstance(raw, tuple) and len(raw) == 2:
        return ProcessOutput(raw[0], raw[1])
    raise TypeError(
        "Spawned process must return ProcessOutput(value, status) or a (value, status) tuple"
    )


def _collect_candidate_keys(
    neighbor_maps: NeighborhoodField[dict[K, bool]],
    new_keys: set[K],
) -> list[K]:
    """Return all active or newly generated keys in deterministic order."""
    seen: set[K] = set(new_keys)
    for proc_map in neighbor_maps.data.values():
        for key, is_active in proc_map.items():
            if is_active:
                seen.add(key)
    try:
        return sorted(seen)  # type: ignore[type-var]
    except TypeError:
        return list(seen)


def _has_neighbor_with_state(
    neighbor_maps: NeighborhoodField[dict[K, bool]],
    key: K,
    expected: bool,
) -> bool:
    """Check whether any peer neighbor currently advertises ``key: expected``."""
    return any(
        proc_map.get(key) is expected
        for proc_map in neighbor_maps.exclude_self().values()
    )


def _evaluate_candidates(
    process: Callable[..., Any],
    candidate_keys: list[K],
    new_keys: set[K],
    args: A,
    neighbor_maps: NeighborhoodField[dict[K, bool]],
) -> tuple[dict[K, bool], dict[K, Any]]:
    """Run candidate processes and compute ``(next_state_map, outputs)``."""
    local_prev: dict[K, bool] = neighbor_maps.local() or {}
    next_state: dict[K, bool] = {}
    outputs: dict[K, Any] = {}

    # Propagate refractory termination for keys that were already closing locally
    for key, was_active in local_prev.items():
        if was_active is False and _has_neighbor_with_state(neighbor_maps, key, True):
            next_state[key] = False

    for key in candidate_keys:
        was_in_bubble = local_prev.get(key) is not None or key in new_keys
        neighbor_closing = _has_neighbor_with_state(neighbor_maps, key, False)
        if local_prev.get(key) is False or (was_in_bubble and neighbor_closing):
            if local_prev.get(key) is not False or _has_neighbor_with_state(
                neighbor_maps, key, True
            ):
                next_state[key] = False
            continue

        with _ProcessTransaction(key) as tx:
            out = _invoke_process(process, key, args)
            status = out.normalized_status()
            if status in (ProcessStatus.OUTPUT, ProcessStatus.BUBBLE):
                tx.commit()
                next_state[key] = True
                if status == ProcessStatus.OUTPUT:
                    outputs[key] = out.value
            elif status == ProcessStatus.TERMINATED:
                next_state[key] = False

    return next_state, outputs


@aggregate
def spawn(
    process: Callable[..., ProcessOutput[R] | tuple[R, ProcessStatus | bool]],
    keys: Iterable[K],
    args: A = None,
) -> dict[K, R]:
    """
    Dynamically spawn and manage spatially scoped aggregate processes.

    Each key ``k`` in ``keys`` (or received from active neighbors) runs ``process(k, args)``
    (or ``process(k)`` if ``process`` takes one parameter) in an isolated alignment scope:

    - ``OUTPUT`` (or ``True``): keeps the process alive in the bubble, propagates ``k``
      to neighbors, and includes ``k: value`` in the returned dictionary;
    - ``BUBBLE``: keeps the process alive and propagates ``k`` to neighbors without
      emitting ``k`` in the local output dictionary;
    - ``EXTERNAL`` (or ``False``): discards internal messages and state for ``k`` on the
      current device and does not propagate ``k``;
    - ``TERMINATED``: initiates a termination wave that cleanly shuts down the entire
      bubble for ``k`` without re-infection.

    Args:
        process: Aggregate process callable returning ``ProcessOutput`` or ``(value, status)``.
        keys: Iterable of process keys to generate on the current device in this round.
        args: Optional argument passed to ``process`` on each device.

    Returns:
        Dictionary mapping each active ``OUTPUT`` process key to its local result.
    """
    new_keys: set[K] = set(keys)
    init_map: dict[K, bool] = {}
    set_field, neighbor_maps = exchange(init_map)
    candidate_keys = _collect_candidate_keys(neighbor_maps, new_keys)
    next_state, outputs = _evaluate_candidates(
        process, candidate_keys, new_keys, args, neighbor_maps
    )
    set_field(next_state)
    return outputs

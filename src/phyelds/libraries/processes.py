"""
Aggregate processes library.

Supports spawning dynamic, spatially and temporally scoped aggregate computations
identified by keys, using either the Pythonic ``@process`` decorator with guard
functions (``in_bubble``, ``terminate_if``, ``emit_if``) / ``with bubble(...):``
or explicit ``ProcessOutput`` values.
"""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import inspect
from typing import Any, Generic, TypeVar

from phyelds import engine
from phyelds.calculus import aggregate, exchange
from phyelds.data import NeighborhoodField

K = TypeVar("K")
R = TypeVar("R")


class ProcessStatus(Enum):
    """Lifecycle status of an aggregate process on the local device."""

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


class _BubbleExit(Exception):
    """Internal control-flow signal raised when a node leaves or terminates a bubble."""

    def __init__(self, status: ProcessStatus) -> None:
        super().__init__(status)
        self.status = status


class _ProcessTransaction:
    """Isolate the alignment path and state/message side effects of one process key."""

    def __init__(self, key: Any) -> None:
        self.key = key
        self.committed = False
        self.should_emit = True
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
        _ACTIVE_TRANSACTIONS.append(self)
        return self

    def commit(self) -> None:
        """Commit state updates and outgoing messages produced by the process."""
        self.committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if _ACTIVE_TRANSACTIONS:
            _ACTIVE_TRANSACTIONS.pop()
        state = self._engine.engine_state
        if state.stack:
            state.stack.pop()
            state.count_stack.pop()
        if not self.committed:
            state.to_send = self._saved_to_send
            state.state_trace = self._saved_state_trace
            state.reads = self._saved_reads


_ACTIVE_TRANSACTIONS: list[_ProcessTransaction] = []


def in_bubble(condition: bool) -> None:
    """
    Declare that the current device belongs to the process bubble only if ``condition`` holds.

    When ``condition`` is False, execution of the process stops immediately for this
    device (``EXTERNAL``), discarding any state and messages produced so far.

    Args:
        condition: True if the current device is inside the bubble.
    """
    if not condition:
        raise _BubbleExit(ProcessStatus.EXTERNAL)


def leave() -> None:
    """Immediately exit the current process bubble as ``EXTERNAL``."""
    raise _BubbleExit(ProcessStatus.EXTERNAL)


def terminate_if(condition: bool) -> None:
    """
    Trigger termination of the entire process bubble when ``condition`` holds.

    Args:
        condition: True to initiate a termination wave for the current process key.
    """
    if condition:
        raise _BubbleExit(ProcessStatus.TERMINATED)


def terminate() -> None:
    """Immediately trigger termination of the entire process bubble (``TERMINATED``)."""
    raise _BubbleExit(ProcessStatus.TERMINATED)


def emit_if(condition: bool) -> None:
    """
    Control whether the current device emits the process value in the ``spawn`` output dict.

    When ``condition`` is False, the device still participates in and relays the process
    bubble (``BUBBLE`` status), but its local value is omitted from the returned dict.

    Args:
        condition: True to emit the output (``OUTPUT``), False for a silent relay (``BUBBLE``).
    """
    if _ACTIVE_TRANSACTIONS:
        _ACTIVE_TRANSACTIONS[-1].should_emit = bool(condition)


@contextmanager
def bubble(
    *,
    inside: bool = True,
    terminate: bool = False,  # pylint: disable=redefined-outer-name
    emit: bool = True,
) -> Iterator[None]:
    """
    Context manager declaring the spatial/temporal boundary of a ``@process`` body.

    Checks ``terminate`` first, then ``inside`` (exiting immediately if False so the
    body inside the ``with`` block only runs on nodes inside the bubble), and sets
    ``emit`` for the returned value.

    Args:
        inside: True if the current node belongs to the bubble.
        terminate: True to shut down the entire bubble across the network.
        emit: True to include this node's result in the output dictionary.
    """
    terminate_if(terminate)
    in_bubble(inside)
    emit_if(emit)
    yield


def process(func: Callable[..., R]) -> Any:
    """
    Decorate a function as an aggregate process and attach ``.spawn(keys, *args, **kwargs)``.

    Inside a ``@process`` function, return plain values directly and control the
    bubble lifecycle with ``in_bubble(...)``, ``terminate_if(...)``, ``emit_if(...)``,
    or ``with bubble(...):``.
    """
    agg_func: Any = aggregate(func)

    def spawn_method(keys: Iterable[Any], *call_args: Any, **call_kwargs: Any) -> dict[Any, R]:
        return spawn(agg_func, keys, *call_args, **call_kwargs)

    agg_func.spawn = spawn_method
    return agg_func


def _call_process_fn(
    proc_fn: Callable[..., Any],
    key: K,
    call_args: tuple[Any, ...],
    call_kwargs: dict[str, Any],
) -> Any:
    """Invoke ``proc_fn`` with ``key`` and any extra positional/keyword arguments."""
    try:
        params = list(inspect.signature(proc_fn).parameters.values())
    except (TypeError, ValueError):
        params = []

    param_names = {p.name for p in params}
    if not call_args and set(call_kwargs.keys()) == {"args"} and "args" not in param_names:
        return proc_fn(key, call_kwargs["args"])

    if not call_args and not call_kwargs:
        positional_kinds = (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        required = [
            p
            for p in params
            if p.kind in positional_kinds and p.default is inspect.Parameter.empty
        ]
        if len(required) >= 2:
            return proc_fn(key, None)
    return proc_fn(key, *call_args, **call_kwargs)


def _invoke_process(
    proc_fn: Callable[..., Any],
    key: K,
    tx: _ProcessTransaction,
    call_args: tuple[Any, ...],
    call_kwargs: dict[str, Any],
) -> ProcessOutput[Any]:
    """Run ``proc_fn`` catching early-exit signals and normalize its return value."""
    try:
        raw = _call_process_fn(proc_fn, key, call_args, call_kwargs)
    except _BubbleExit as exit_signal:
        return ProcessOutput(None, exit_signal.status)

    if isinstance(raw, ProcessOutput):
        return raw
    if (
        isinstance(raw, tuple)
        and len(raw) == 2
        and (type(raw[1]) is bool or isinstance(raw[1], ProcessStatus))  # pylint: disable=unidiomatic-typecheck
    ):
        return ProcessOutput(raw[0], raw[1])
    status = ProcessStatus.OUTPUT if tx.should_emit else ProcessStatus.BUBBLE
    return ProcessOutput(raw, status)


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


def _evaluate_candidates(  # pylint: disable=too-many-arguments
    proc_fn: Callable[..., Any],
    candidate_keys: list[K],
    new_keys: set[K],
    neighbor_maps: NeighborhoodField[dict[K, bool]],
    *,
    call_args: tuple[Any, ...],
    call_kwargs: dict[str, Any],
) -> tuple[dict[K, bool], dict[K, Any]]:
    """Run candidate processes and compute ``(next_state_map, outputs)``."""
    local_prev: dict[K, bool] = neighbor_maps.local() or {}
    next_state: dict[K, bool] = {
        key: False
        for key, was_active in local_prev.items()
        if was_active is False and _has_neighbor_with_state(neighbor_maps, key, True)
    }
    outputs: dict[K, Any] = {}

    for key in candidate_keys:
        was_in_bubble = local_prev.get(key) is not None or key in new_keys
        if local_prev.get(key) is False or (
            was_in_bubble and _has_neighbor_with_state(neighbor_maps, key, False)
        ):
            if local_prev.get(key) is not False or _has_neighbor_with_state(
                neighbor_maps, key, True
            ):
                next_state[key] = False
            continue

        with _ProcessTransaction(key) as tx:
            out = _invoke_process(proc_fn, key, tx, call_args, call_kwargs)
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
    proc_fn: Callable[..., Any],
    keys: Iterable[K],
    *call_args: Any,
    **call_kwargs: Any,
) -> dict[K, Any]:
    """
    Dynamically spawn and manage spatially scoped aggregate processes.

    Supports both ``@process`` functions (using ``in_bubble``, ``terminate_if``,
    ``emit_if``, or ``with bubble(...):`` and returning plain values) and functions
    returning ``ProcessOutput`` or ``(value, status)`` tuples.

    Args:
        proc_fn: Aggregate process callable.
        keys: Iterable of process keys to generate on the current device in this round.
        *call_args: Positional arguments forwarded to ``proc_fn`` after ``key``.
        **call_kwargs: Keyword arguments forwarded to ``proc_fn``.

    Returns:
        Dictionary mapping each active ``OUTPUT`` process key to its local result.
    """
    new_keys: set[K] = set(keys)
    init_map: dict[K, bool] = {}
    set_field, neighbor_maps = exchange(init_map)
    candidate_keys = _collect_candidate_keys(neighbor_maps, new_keys)
    next_state, outputs = _evaluate_candidates(
        proc_fn,
        candidate_keys,
        new_keys,
        neighbor_maps,
        call_args=call_args,
        call_kwargs=call_kwargs,
    )
    set_field(next_state)
    return outputs

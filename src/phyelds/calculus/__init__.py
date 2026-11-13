"""
Core syntax of phyelds: the primitives aggregate programs are made of.

`@aggregate` marks a function as an aggregate function:

```python
@aggregate
def my_function():
    ...
```

Inside it, the core syntax is:

- `remember`: keeps a value across rounds.
- `remember_and_evolve`: keeps a value across rounds, updating it with a function.
- `neighbors`: shares a value with the neighbors and returns their values.
- `exchange`: evolves a state and sends values (possibly distinct per neighbor) in one step.
- `align`: scopes the calls inside it, so that they only align with the same scope on the neighbors.
"""
import functools
from typing import TypeVar, Callable, Tuple, Union, Any

from phyelds import engine
from phyelds.calculus.align import AlignContext
from phyelds.data import NeighborhoodField

try:
    from phyelds.calculus.internal.transform import (  # noqa: F401 (str_transformed_code is public)
        transform_code, str_transformed_code,
    )
except ImportError:
    # The MicroPython bundle has no ``ast``: its code is rewritten when it is built, aligned.
    transform_code = None


# Generic type variable to preserve types through functions
T = TypeVar("T")


def aggregate(func):
    """
    Mark a function as an aggregate function, returning a wrapper that aligns its calls.

    Each call enters a new alignment point named after the function, so the values a
    device shares inside it only meet those of neighbors running the same call. The
    branches of the ``if`` statements and conditional expressions in its body are
    aligned too, so devices on different branches do not exchange values.

    Example:
        ```python
        @aggregate
        def my_function():
            ...
        ```

    Args:
        func (Callable): The function to wrap.
    """

    # Aligned and vectorized, rewritten on the first call of each, once: the rewriting is costly.
    rewritten = [None, None]

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        current_engine = engine.get()
        vectorized = current_engine.vectorized
        function = rewritten[vectorized]
        if function is None:
            function = rewritten[vectorized] = _transformed(func, vectorized)
        current_engine.enter(func.__name__)
        result = function(*args, **kwargs)
        current_engine.exit()
        return result

    return wrapper


def remember(init: T) -> Tuple[T, Callable[[T], T]]:
    """
    Keep a value across the rounds of the current device.

    On the first round the state holds ``init``; afterwards it holds the value last
    passed to the update function.

    Example:
        ```python
        count, set_count = remember(0)
        count = set_count(count + 1)  # count is now 1 more than in the previous round
        ```

    Args:
        init: The value of the state on the first round.

    Returns:
        A tuple ``(state, set_state)``: ``state`` is the current value, and
            ``set_state`` stores a new value for the next round and returns it.
    """
    current_engine = engine.get()
    current_engine.enter("remember")
    path = current_engine.current_path()
    value: T = current_engine.read_state_or(init, path)
    current_engine.exit()

    def set_state(new_value: T) -> T:
        current_engine.write_state(new_value, path)
        return new_value

    return value, set_state


def remember_and_evolve(
        init: T,
        evolve_fn: Callable[[T], T]
) -> T:
    """
    Keep a value across rounds, replacing it every round with ``evolve_fn`` of itself.

    Example:
        ```python
        rounds = remember_and_evolve(0, lambda count: count + 1)  # 1 on the first round
        ```

    Args:
        init: The value the state starts from, before the first evolution.
        evolve_fn: Function that receives the current value and returns the new value.

    Returns:
        The value after this round's evolution: ``evolve_fn(init)`` on the first round.
    """
    current_engine = engine.get()
    updated: T = evolve_fn(current_engine.read_state_or(init))
    current_engine.write_state(updated)
    return updated


@aggregate
def neighbors(value: T) -> "NeighborhoodField[T]":
    """
    Share ``value`` with the neighbors and gather the values they shared at this point.

    Example:
        ```python
        temperatures = neighbors(sense("temperature"))  # one temperature per neighbor
        hottest = temperatures.max()
        ```

    Args:
        value: The local value to share; it cannot be a ``NeighborhoodField``.

    Returns:
        A ``NeighborhoodField`` mapping the current device and each neighbor that
            shared a value at the same alignment point to that value.

    Raises:
        TypeError: If ``value`` is a ``NeighborhoodField``.
    """
    if isinstance(value, NeighborhoodField):
        raise TypeError("Neighborhood is not supported as a value")

    current_engine = engine.get()
    current_engine.send(value)
    return current_engine.neighbor_field(value)


def _extract_for_node(value: Any, node_id: int) -> Any:
    """Extract the value addressed to ``node_id`` from a scalar or field."""
    if isinstance(value, NeighborhoodField):
        return value.for_node(node_id)
    return value


@aggregate
def exchange(
    init: Union[T, "NeighborhoodField[T]"],
) -> Tuple[T, "NeighborhoodField[T]", Callable[[Any], Any]]:
    """
    Exchange values with neighbors and across rounds at the current alignment point.

    Args:
        init: Initial value (or field) used when no previous value is available.

    Returns:
        A tuple ``(local, field, send)`` containing the local state value, the
            ``NeighborhoodField`` received in the current round, and the send function
            for the next round.
    """
    current_engine = engine.get()
    path = current_engine.current_path()
    node_id = current_engine.node_context.node_id
    state = current_engine.read_state_or(init, path)
    current_engine.send(state, path)
    default_value = (
        init.default
        if isinstance(init, NeighborhoodField)
        else _extract_for_node(init, node_id)
    )
    local_value = _extract_for_node(state, node_id)
    field = current_engine.neighbor_field(local_value, path, default_value, addressed=True)

    def send(new_value: Any) -> Any:
        current_engine.write_state(new_value, path)
        current_engine.send(new_value, path)
        return new_value

    return local_value, field, send


def align(name: Any):
    """
    Scope a block of code under ``name``, as a context manager.

    The calls inside the block only align with the calls made inside a block with the
    same name on the neighbors, so devices in blocks with different names do not
    exchange values there.

    Example:
        ```python
        with align(sense("team")):
            members = neighbors(1).sum()  # counts only the neighbors in the same team
        ```

    Args:
        name: The key of the block; it is converted with ``str``.

    Returns:
        A context manager that enters the block on ``with`` and leaves it on exit.
    """
    return AlignContext(str(name))


def align_right():
    """
    Scope the ``else`` branch of a conditional, as ``align("right")``.

    ``@aggregate`` already aligns the branches of ``if`` statements and conditional
    expressions; ``align_left`` and ``align_right`` do it by hand.

    Example:
        ```python
        if condition:
            with align_left():
                ...  # devices where condition holds
        else:
            with align_right():
                ...  # the other devices
        ```
    """
    return align("right")


def align_left():
    """
    Scope the ``if`` branch of a conditional, as ``align("left")``; see ``align_right``.
    """
    return align("left")


def _aligned_branch(condition: Any, if_true: Callable[[], T], if_false: Callable[[], T]) -> T:
    """
    Evaluate a conditional expression like an ``if`` statement: the branch chosen by
    ``condition`` runs in ``align_left`` or ``align_right``, so devices on different
    branches do not exchange values. ``@aggregate`` rewrites ``a if c else b`` into a
    call to this function.
    """
    return engine.get().branch(condition, if_true, if_false)


def _transformed(func: Callable, vectorized: bool = False) -> Callable:
    """
    ``func`` rewritten: with its branches aligned, or for a vectorized engine; as it is if
    it was already rewritten at build time.
    """
    if transform_code is None:
        return func
    return transform_code(
        func,
        {"align_left": align_left, "align_right": align_right, "_aligned_branch": _aligned_branch},
        vectorized,
    )

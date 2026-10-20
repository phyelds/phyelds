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
from phyelds.data import State, NeighborhoodField

try:
    from phyelds.calculus.internal.transform import (  # noqa: F401 (str_transformed_code is public)
        transform_code, str_transformed_code,
    )
except ImportError:
    # The MicroPython bundle has no ``ast``: its code is rewritten when it is built.
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

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        engine.get().enter(func.__name__)
        result = _transformed(func)(*args, **kwargs)
        engine.get().exit()
        return result

    return wrapper


@aggregate
def remember(init: T) -> Tuple[Callable[[Union[T, "State[T]"]], "State[T]"], "State[T]"]:
    """
    Keep a value across the rounds of the current device.

    On the first round the state holds ``init``; afterwards it holds the value last
    passed to the update function.

    Example:
        ```python
        set_count, count = remember(0)
        set_count(count + 1)  # count is now 1 more than in the previous round
        ```

    Args:
        init: The value of the state on the first round.

    Returns:
        A tuple ``(set_state, state)``: ``set_state`` stores a new value (which ``state``
            reflects at once) and returns ``state``; ``state`` is a ``State`` proxy that
            behaves like the value it holds.
    """
    # engine.get() returns the context/engine instance
    state = State(init, engine.get().current_path(), engine.get())
    return state.update_fn, state


def remember_and_evolve(
        init: T,
        evolve_fn: Callable[["State[T]"], T]
) -> "State[T]":
    """
    Keep a value across rounds, replacing it every round with ``evolve_fn`` of itself.

    Example:
        ```python
        rounds = remember_and_evolve(0, lambda count: count + 1)  # 1 on the first round
        ```

    Args:
        init: The value the state starts from, before the first evolution.
        evolve_fn: Function that receives the current ``State`` and returns the new value.

    Returns:
        The ``State`` after this round's evolution: ``evolve_fn(init)`` on the first round.
    """
    state = State(init, engine.get().current_path(), engine.get())
    # evolve_fn takes the state and returns the new value (T)
    # state.update_fn takes the new value and returns the State object
    state.update_fn(evolve_fn(state))
    return state


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

    engine.get().send(value)

    # aligned_values returns a Dict[int, Any], strictly speaking Dict[int, T] here
    values = engine.get().aligned_values(engine.get().current_path())
    values[engine.get().node_context.node_id] = value

    return NeighborhoodField(values, engine.get().node_context.node_id)


def _extract_for_node(value: Any, node_id: int) -> Any:
    """Extract the value addressed to ``node_id`` from a scalar, ``State``, or field."""
    if isinstance(value, State):
        value = value.value
    if isinstance(value, NeighborhoodField):
        return value.for_node(node_id)
    return value


@aggregate
def exchange(
    init: Union[T, "NeighborhoodField[T]"],
) -> Tuple[Callable[[Any], Any], "NeighborhoodField[T]"]:
    """
    Exchange values with neighbors and across rounds at the current alignment point.

    Args:
        init: Initial value (or field) used when no previous value is available.

    Returns:
        A tuple ``(set_field, field)`` containing the send function for the next round
            and the ``NeighborhoodField`` received in the current round.
    """
    current_engine = engine.get()
    path = current_engine.current_path()
    node_id = current_engine.node_context.node_id
    stored = current_engine.read_state(path)
    if stored is None:
        raw_init = init.value if isinstance(init, State) else init
        local_value = _extract_for_node(raw_init, node_id)
        current_engine.write_state(raw_init, path)
        current_engine.send(raw_init, path)
    else:
        local_value = _extract_for_node(stored, node_id)
        current_engine.send(stored, path)

    values = {
        neighbor_id: _extract_for_node(neighbor_value, node_id)
        for neighbor_id, neighbor_value in current_engine.aligned_values(path).items()
    }
    values[node_id] = local_value
    default_value = (
        init.default
        if isinstance(init, NeighborhoodField)
        else _extract_for_node(init, node_id)
    )
    field = NeighborhoodField(values, node_id, default=default_value)

    def set_field(new_value: Any) -> Any:
        raw_new = new_value.value if isinstance(new_value, State) else new_value
        current_engine.write_state(raw_new, path)
        current_engine.send(raw_new, path)
        return new_value

    return set_field, field


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
    if condition:
        with align_left():
            return if_true()
    with align_right():
        return if_false()


def _transformed(func: Callable) -> Callable:
    """``func`` with its branches aligned, unless it was already rewritten at build time."""
    if transform_code is None:
        return func
    return transform_code(
        func,
        {"align_left": align_left, "align_right": align_right, "_aligned_branch": _aligned_branch},
    )

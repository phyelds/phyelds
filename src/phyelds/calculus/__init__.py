"""
Core syntax for phyelds.
It exposes a set of functions that are used to create and manipulate fields,
as well as to manage the state of the system.
@aggregate is a decorator that marks a function as an aggregate function,
Example:
@aggregate
def my_function():
    # do something
    return result

Then, there is the core syntax of phyelds:
- remember: used to remember a value across iterations.
- neighbors: used to get the neighbors of a node.
- exchange: used to exchange values (or anisotropic fields) across iterations and neighbors.
- neighbors_distances: used to get the distances to the neighbors.
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
    A decorator for aggregate functions,
    namely each function that is called in the context of a field.
    You can use it in the following way:
    @aggregate
    def my_function():
        # do something
        return result
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
    One of the main operator of phyelds.

    :param init: The initial value for the state.
    :return: A tuple containing the update function and the state object.
    """
    # engine.get() returns the context/engine instance
    state = State(init, engine.get().current_path(), engine.get())
    return state.update_fn, state


def remember_and_evolve(
        init: T,
        evolve_fn: Callable[["State[T]"], T]
) -> "State[T]":
    """
    Remember a value across iterations and evolve it using the provided function.

    :param init: Initial value to remember.
    :param evolve_fn: Function to evolve the remembered value.
                      It receives the current State object and should return the new value.
    :return: The updated State object.
    """
    state = State(init, engine.get().current_path(), engine.get())
    # evolve_fn takes the state and returns the new value (T)
    # state.update_fn takes the new value and returns the State object
    state.update_fn(evolve_fn(state))
    return state


@aggregate
def neighbors(value: T) -> "NeighborhoodField[T]":
    """
    Get the `value` of the neighbors from the current node.
    Example:
    neighbors(context.data["temperature"]) // returns the temperature of the neighbors
    :param value: used to query the neighbors.
    :return: the neighborhood representing this value containing data of type T
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
    Used to align a part of the code with the current context,
    creating different non communicating zones
    :param name: symbol you would like to align on
    :return: the context
    """
    return AlignContext(str(name))


def align_right():
    """
    Typically used in if statements to align the code
    Example:
    if condition:
        with align_left():
            # do something
    else:
        with align_right():
            # do something else
    :return:
    """
    return align("right")


def align_left():
    """
    Typically used in if statements to align the code
    See align_right
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

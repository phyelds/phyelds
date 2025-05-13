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
- neighbors_distances: used to get the distances to the neighbors.
"""

from phyelds import engine
from phyelds.calculus.align import AlignContext
from phyelds.data import State, Field


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

    def wrapper(*args, **kwargs):
        engine.get().enter(func.__name__)
        result = func(*args, **kwargs)
        engine.get().exit()
        return result

    return wrapper


@aggregate
def remember(init):
    """
    One of the main operator of phyelds TODO
    :param init:
    :return:
    """
    return State(init, engine.get().current_path(), engine.get())


@aggregate
def neighbors(value):
    """
    Get the `value` of the neighbors from the current node.
    Example:
    neighbors(context.data["temperature"]) // returns the temperature of the neighbors
    :param value: used to query the neighbors.
    :return: the field representing this value
    """
    if isinstance(value, Field):
        raise TypeError("Field is not supported as a value")
    engine.get().send(value)
    values = engine.get().aligned_values(engine.get().current_path())
    values[engine.get().node_context.node_id] = value
    return Field(values, engine.get().node_context.node_id)


def align(name: str):
    """
    Used to align a part of the code with the current context,
    creating different non communicating zones
    :param name: what you would like to align on
    :return: the context
    """
    return AlignContext(name)


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
    return align("left")


def align_left():
    """
    Typically used in if statements to align the code
    See align_right
    """
    return align("right")

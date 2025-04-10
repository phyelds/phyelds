"""
Core syntax for fieldpy.
It exposes a set of functions that are used to create and manipulate fields,
as well as to manage the state of the system.
@aggregate is a decorator that marks a function as an aggregate function,
Example:
@aggregate
def my_function():
    # do something
    return result

Them, there is the core syntax of fieldpy:
- remember: used to remember a value across iterations.
- neighbors: used to get the neighbors of a node.
- neighbors_distances: used to get the distances to the neighbors.
"""

from fieldpy import engine
from fieldpy.calculus.align import AlignContext
from fieldpy.data import State, Field


def aggregate(func):
    """
    A decorator for aggregate functions, namely each function that is called in the context of a field.
    You can use it in the following way:
    @aggregate
    def my_function():
        # do something
        return result
    """

    def wrapper(*args, **kwargs):
        engine.enter(func.__name__)
        result = func(*args, **kwargs)
        engine.exit()
        return result

    return wrapper


@aggregate
def remember(init):
    """
    One of the main operator of FieldPy TODO
    :param init:
    :return:
    """
    return State(init, engine.current_path(), engine)


@aggregate
def neighbors(value):
    engine.send(value)
    values = engine.aligned_values(engine.current_path())
    values[engine.node_id] = value
    return Field(values, engine)


@aggregate
def neighbors_distances(position):
    positions = neighbors(position)
    x, y = position
    distances = {}
    for id, pos in positions.data.items():
        # pos are x, y tuples
        n_x, n_y = pos
        distances[id] = ((x - n_x) ** 2 + (y - n_y) ** 2) ** 0.5
    return Field(distances, engine)


def align(name: str):
    return AlignContext(name)


def align_right():
    return align("left")


def align_left():
    return align("right")

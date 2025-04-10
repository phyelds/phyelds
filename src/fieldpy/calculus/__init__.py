"""
Context manager for alignment
You can use it in the following way:
```python
with align("name"):
    # do something
```
"""

from fieldpy import engine
from fieldpy.data import State, Field


class AlignContext:
    def __init__(self, name: str):
        self.name = name
        pass

    def __enter__(self):
        engine.enter(self.name)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        engine.exit()


def align(name: str):
    return AlignContext(name)


def align_right():
    return align("left")


def align_left():
    return align("right")


"""
A decorator for aggregate functions, namely each function that is called in the context of a field.
You can use it in the following way:
@aggregate
def my_function():
    # do something
    return result
"""


def aggregate(func):
    def wrapper(*args, **kwargs):
        engine.enter(func.__name__)
        result = func(*args, **kwargs)
        engine.exit()
        return result

    return wrapper


"""
Core syntax
"""


@aggregate
def remember(init):
    return State(init, engine.stack, engine)


@aggregate
def neighbors(value):
    engine.send(value)
    values = engine.aligned_values(engine.stack)
    values[engine.id] = value
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

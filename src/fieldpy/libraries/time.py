"""
A group of functions based on the notion of time.
"""

from fieldpy.calculus import aggregate, remember


@aggregate
def counter():
    return remember(0).update_fn(lambda x: x + 1)

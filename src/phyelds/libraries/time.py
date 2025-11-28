"""
A group of functions based on the notion of time.
"""

from phyelds.calculus import aggregate, remember_and_evolve
from phyelds.data import State


@aggregate
def counter() -> State[int]:
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)

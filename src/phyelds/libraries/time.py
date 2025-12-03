"""
A group of functions based on the notion of time.
"""

from phyelds.calculus import aggregate, remember_and_evolve
from phyelds.data import StateT


@aggregate
def counter() -> StateT[int]:
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)

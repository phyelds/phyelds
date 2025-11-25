"""
A group of functions based on the notion of time.
"""

from phyelds.calculus import aggregate, remember, remember_and_evolve


@aggregate
def counter():
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)

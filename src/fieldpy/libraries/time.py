"""
A group of functions based on the notion of time.
"""

from fieldpy.calculus import aggregate, remember


@aggregate
def counter():
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember(0).update_fn(lambda x: x + 1)

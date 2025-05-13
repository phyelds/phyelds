"""
This module contains utility functions and classes for various purposes.
"""


def min_with_default(iterable, default=None):
    """
    Returns the minimum value from an iterable, or a default value if the iterable is empty.
    :param iterable: a list of values (or any iterable)
    :param default: the default value to return if the iterable is empty
    :return: the minimum value from the iterable or the default value
    """
    if not iterable:
        return default
    if isinstance(iterable, dict):
        return min(iterable.values())
    if isinstance(iterable, (list, tuple, set, range)):
        return min(iterable)
    return default

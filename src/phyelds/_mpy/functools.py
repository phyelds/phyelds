"""Stand-in for ``functools``: MicroPython functions cannot take attributes."""
from collections.abc import Callable


def wraps(_wrapped: Callable) -> Callable:
    """Return the wrapper unchanged."""
    return lambda wrapper: wrapper


def update_wrapper(wrapper: object, _wrapped: Callable) -> object:
    """Return ``wrapper`` unchanged."""
    return wrapper

"""
Stand-in for ``operator``: the binary operators phyelds passes as reductions, such as
``operator.add`` to ``fold``, as plain functions.
"""
from typing import Any


def add(first: Any, second: Any) -> Any:
    """``first + second``."""
    return first + second


def sub(first: Any, second: Any) -> Any:
    """``first - second``."""
    return first - second


def mul(first: Any, second: Any) -> Any:
    """``first * second``."""
    return first * second


def truediv(first: Any, second: Any) -> Any:
    """``first / second``."""
    return first / second


def and_(first: Any, second: Any) -> Any:
    """``first & second``."""
    return first & second


def or_(first: Any, second: Any) -> Any:
    """``first | second``."""
    return first | second


def eq(first: Any, second: Any) -> Any:
    """``first == second``."""
    return first == second


def ne(first: Any, second: Any) -> Any:
    """``first != second``."""
    return first != second


def lt(first: Any, second: Any) -> Any:
    """``first < second``."""
    return first < second


def le(first: Any, second: Any) -> Any:
    """``first <= second``."""
    return first <= second


def gt(first: Any, second: Any) -> Any:
    """``first > second``."""
    return first > second


def ge(first: Any, second: Any) -> Any:
    """``first >= second``."""
    return first >= second

"""
Stand-in for ``wrapt``: an ``ObjectProxy`` that forwards attributes and operators.

Unlike ``wrapt``, the proxy does not pretend to be of the type it wraps:
``isinstance(proxy, int)`` is false.
"""
from typing import Any


def _unwrap(value: Any) -> Any:
    return value.__wrapped__ if isinstance(value, ObjectProxy) else value


def _forward(operator):
    return lambda self, other: operator(self.__wrapped__, _unwrap(other))


def _reflect(operator):
    return lambda self, other: operator(_unwrap(other), self.__wrapped__)


class ObjectProxy:
    """Forwards to ``__wrapped__``; attributes named ``_self_*`` stay on the proxy."""

    def __init__(self, wrapped: Any):
        self.__wrapped__ = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__wrapped__, name)

    __add__ = _forward(lambda a, b: a + b)
    __sub__ = _forward(lambda a, b: a - b)
    __mul__ = _forward(lambda a, b: a * b)
    __truediv__ = _forward(lambda a, b: a / b)
    __floordiv__ = _forward(lambda a, b: a // b)
    __mod__ = _forward(lambda a, b: a % b)
    __pow__ = _forward(lambda a, b: a ** b)
    __and__ = _forward(lambda a, b: a & b)
    __or__ = _forward(lambda a, b: a | b)
    __xor__ = _forward(lambda a, b: a ^ b)
    __lshift__ = _forward(lambda a, b: a << b)
    __rshift__ = _forward(lambda a, b: a >> b)
    __radd__ = _reflect(lambda a, b: a + b)
    __rsub__ = _reflect(lambda a, b: a - b)
    __rmul__ = _reflect(lambda a, b: a * b)
    __rtruediv__ = _reflect(lambda a, b: a / b)
    __rfloordiv__ = _reflect(lambda a, b: a // b)
    __rmod__ = _reflect(lambda a, b: a % b)
    __rpow__ = _reflect(lambda a, b: a ** b)
    __rand__ = _reflect(lambda a, b: a & b)
    __ror__ = _reflect(lambda a, b: a | b)
    __rxor__ = _reflect(lambda a, b: a ^ b)
    __eq__ = _forward(lambda a, b: a == b)
    __ne__ = _forward(lambda a, b: a != b)
    __lt__ = _forward(lambda a, b: a < b)
    __le__ = _forward(lambda a, b: a <= b)
    __gt__ = _forward(lambda a, b: a > b)
    __ge__ = _forward(lambda a, b: a >= b)
    __contains__ = _forward(lambda a, b: b in a)
    __getitem__ = _forward(lambda a, b: a[b])

    def __neg__(self) -> Any:
        return -self.__wrapped__

    def __pos__(self) -> Any:
        return +self.__wrapped__

    def __abs__(self) -> Any:
        return abs(self.__wrapped__)

    def __invert__(self) -> Any:
        return ~self.__wrapped__

    def __bool__(self) -> bool:
        return bool(self.__wrapped__)

    def __len__(self) -> int:
        return len(self.__wrapped__)

    def __iter__(self) -> Any:
        return iter(self.__wrapped__)

    def __hash__(self) -> int:
        return hash(self.__wrapped__)

    def __int__(self) -> int:
        return int(self.__wrapped__)

    def __float__(self) -> float:
        return float(self.__wrapped__)

    def __index__(self) -> int:
        return self.__wrapped__.__index__()

    def __str__(self) -> str:
        return str(self.__wrapped__)

    def __repr__(self) -> str:
        return repr(self.__wrapped__)

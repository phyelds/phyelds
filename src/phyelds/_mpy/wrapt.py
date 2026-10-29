"""
Stand-in for ``wrapt``: an ``ObjectProxy`` that forwards attributes and operators.

Unlike ``wrapt``, the proxy does not pretend to be of the type it wraps:
``isinstance(proxy, int)`` is false.

Each operator is spelled out: built from closures, they would keep about twice the memory.
"""
from typing import Any


def _unwrap(value: Any) -> Any:
    return value.__wrapped__ if isinstance(value, ObjectProxy) else value


class ObjectProxy:
    """Forwards to ``__wrapped__``; attributes named ``_self_*`` stay on the proxy."""

    def __init__(self, wrapped: Any):
        self.__wrapped__ = wrapped

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__wrapped__, name)

    def __add__(self, other: Any) -> Any:
        return self.__wrapped__ + _unwrap(other)

    def __sub__(self, other: Any) -> Any:
        return self.__wrapped__ - _unwrap(other)

    def __mul__(self, other: Any) -> Any:
        return self.__wrapped__ * _unwrap(other)

    def __truediv__(self, other: Any) -> Any:
        return self.__wrapped__ / _unwrap(other)

    def __floordiv__(self, other: Any) -> Any:
        return self.__wrapped__ // _unwrap(other)

    def __mod__(self, other: Any) -> Any:
        return self.__wrapped__ % _unwrap(other)

    def __pow__(self, other: Any) -> Any:
        return self.__wrapped__ ** _unwrap(other)

    def __and__(self, other: Any) -> Any:
        return self.__wrapped__ & _unwrap(other)

    def __or__(self, other: Any) -> Any:
        return self.__wrapped__ | _unwrap(other)

    def __xor__(self, other: Any) -> Any:
        return self.__wrapped__ ^ _unwrap(other)

    def __lshift__(self, other: Any) -> Any:
        return self.__wrapped__ << _unwrap(other)

    def __rshift__(self, other: Any) -> Any:
        return self.__wrapped__ >> _unwrap(other)

    def __radd__(self, other: Any) -> Any:
        return _unwrap(other) + self.__wrapped__

    def __rsub__(self, other: Any) -> Any:
        return _unwrap(other) - self.__wrapped__

    def __rmul__(self, other: Any) -> Any:
        return _unwrap(other) * self.__wrapped__

    def __rtruediv__(self, other: Any) -> Any:
        return _unwrap(other) / self.__wrapped__

    def __rfloordiv__(self, other: Any) -> Any:
        return _unwrap(other) // self.__wrapped__

    def __rmod__(self, other: Any) -> Any:
        return _unwrap(other) % self.__wrapped__

    def __rpow__(self, other: Any) -> Any:
        return _unwrap(other) ** self.__wrapped__

    def __rand__(self, other: Any) -> Any:
        return _unwrap(other) & self.__wrapped__

    def __ror__(self, other: Any) -> Any:
        return _unwrap(other) | self.__wrapped__

    def __rxor__(self, other: Any) -> Any:
        return _unwrap(other) ^ self.__wrapped__

    def __eq__(self, other: Any) -> Any:
        return self.__wrapped__ == _unwrap(other)

    def __ne__(self, other: Any) -> Any:
        return self.__wrapped__ != _unwrap(other)

    def __lt__(self, other: Any) -> Any:
        return self.__wrapped__ < _unwrap(other)

    def __le__(self, other: Any) -> Any:
        return self.__wrapped__ <= _unwrap(other)

    def __gt__(self, other: Any) -> Any:
        return self.__wrapped__ > _unwrap(other)

    def __ge__(self, other: Any) -> Any:
        return self.__wrapped__ >= _unwrap(other)

    def __contains__(self, other: Any) -> Any:
        return _unwrap(other) in self.__wrapped__

    def __getitem__(self, other: Any) -> Any:
        return self.__wrapped__[_unwrap(other)]

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

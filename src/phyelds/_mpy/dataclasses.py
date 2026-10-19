"""
Stand-in for ``dataclasses``.

MicroPython drops class annotations, so the build lists the fields of each dataclass in
``__dataclass_fields__``; their defaults stay class attributes.
"""
from collections.abc import Callable
from typing import Any


def dataclass(cls: type | None = None, *, frozen: bool = False, **_options: Any) -> Any:
    """Add ``__init__``, ``__eq__``, ``__repr__`` and, if ``frozen``, ``__hash__`` to ``cls``."""
    def decorate(cls: type) -> type:
        names = cls.__dataclass_fields__
        defaults = {name: getattr(cls, name) for name in names if hasattr(cls, name)}
        cls.__init__ = _initializer(names, defaults)
        cls.__eq__ = _equal
        cls.__repr__ = lambda self: f"{type(self).__name__}{_values(self)!r}"
        if frozen:
            cls.__hash__ = lambda self: hash(_values(self))
        return cls

    return decorate if cls is None else decorate(cls)


def _equal(instance: Any, other: Any) -> bool:
    """Dataclasses are equal if they have the same type and the same field values."""
    return type(other) is type(instance) and _values(other) == _values(instance)


def _initializer(names: tuple[str, ...], defaults: dict[str, Any]) -> Callable:
    """The ``__init__`` of a dataclass with fields ``names``."""
    def initialize(self, *args, **kwargs):
        values = dict(defaults)
        values.update(zip(names, args))
        values.update(kwargs)
        for name in names:
            if name not in values:
                raise TypeError(f"missing argument: {name}")
            object.__setattr__(self, name, values[name])
        if hasattr(self, "__post_init__"):
            self.__post_init__()

    return initialize


def _values(instance: Any) -> tuple:
    """The values of the fields of ``instance``, in order."""
    return tuple(getattr(instance, name) for name in instance.__dataclass_fields__)

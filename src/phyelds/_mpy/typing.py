"""
Stand-in for ``typing`` and ``collections.abc``: MicroPython ignores annotations.

Every name is a placeholder that can be subscripted, called or combined with ``|``, so
that type aliases and type variables still evaluate.
"""


class _Placeholder:
    """Stands for any type."""

    def __getitem__(self, _item: object) -> "_Placeholder":
        return self

    def __call__(self, *_args: object, **_kwargs: object) -> "_Placeholder":
        return self

    def __or__(self, _other: object) -> "_Placeholder":
        return self

    __ror__ = __or__


_ANY = _Placeholder()


def __getattr__(_name: str) -> _Placeholder:
    return _ANY


def cast(_kind: object, value: object) -> object:
    """Return ``value``."""
    return value

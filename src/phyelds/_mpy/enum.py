"""
Stand-in for ``enum``.

MicroPython has no metaclasses, so the build decorates each ``Enum`` subclass with
``members``, which turns its attributes into members.
"""


class Enum:  # pylint: disable=too-few-public-methods
    """Base of enumerations: each member has a ``name`` and a ``value``."""

    name: str
    value: object

    def __repr__(self) -> str:
        return f"<{type(self).__name__}.{self.name}: {self.value!r}>"


def members(cls: type) -> type:
    """Replace the public, non-callable attributes of ``cls`` with members."""
    for name, value in list(cls.__dict__.items()):
        if name.startswith("_") or callable(value):
            continue
        member = object.__new__(cls)
        member.name, member.value = name, value
        setattr(cls, name, member)
    return cls

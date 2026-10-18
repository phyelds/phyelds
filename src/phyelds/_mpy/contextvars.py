"""Stand-in for ``contextvars``: one context only, as MicroPython runs one device."""
from typing import Any

_MISSING = object()


class ContextVar:
    """A variable with a single value."""

    def __init__(self, name: str, *, default: Any = _MISSING):
        self.name = name
        self._value = default

    def get(self, default: Any = _MISSING) -> Any:
        """The value, or ``default`` if it was never set."""
        if self._value is not _MISSING:
            return self._value
        if default is not _MISSING:
            return default
        raise LookupError(self.name)

    def set(self, value: Any) -> None:
        """Replace the value."""
        self._value = value

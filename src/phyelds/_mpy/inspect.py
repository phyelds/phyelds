"""
Stand-in for ``inspect``: ``signature`` only, for the functions the build recorded.

MicroPython cannot tell the parameters of a function; the build records those of the
functions defined at the top of a program. For the others, ``signature`` raises
``ValueError``, as CPython does for functions it cannot inspect.
"""
from collections import OrderedDict
from collections.abc import Callable

_SIGNATURES = {}


class Parameter:  # pylint: disable=too-few-public-methods
    """A parameter: its ``name``, ``kind`` and ``default`` (``Parameter.empty`` if none)."""

    POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, KEYWORD_ONLY, VAR_KEYWORD = range(5)
    empty = object()

    def __init__(self, name: str, kind: int, has_default: bool):
        self.name = name
        self.kind = kind
        self.default = None if has_default else Parameter.empty


class Signature:  # pylint: disable=too-few-public-methods
    """The parameters of a function, by name, in order."""

    def __init__(self, parameters: tuple[tuple[str, int, bool], ...]):
        self.parameters = OrderedDict((name, Parameter(name, *rest)) for name, *rest in parameters)


def register(function: Callable, parameters: tuple[tuple[str, int, bool], ...]) -> None:
    """Record the ``(name, kind, has_default)`` parameters of ``function``."""
    _SIGNATURES[function] = parameters


def signature(function: Callable) -> Signature:
    """
    The recorded signature of ``function``.

    Raises:
        ValueError: If the parameters of ``function`` were not recorded.
    """
    if function not in _SIGNATURES:
        raise ValueError(f"no signature recorded for {function!r}")
    return Signature(_SIGNATURES[function])

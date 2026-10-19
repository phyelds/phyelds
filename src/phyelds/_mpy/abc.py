"""Stand-in for ``abc``: abstract classes are not enforced."""
from collections.abc import Callable


class ABC:  # pylint: disable=too-few-public-methods
    """Base of abstract classes."""


def abstractmethod(function: Callable) -> Callable:
    """Mark ``function`` as abstract, which changes nothing here."""
    return function

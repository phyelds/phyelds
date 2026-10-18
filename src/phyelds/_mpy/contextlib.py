"""Stand-in for ``contextlib``: ``contextmanager`` only."""
from collections.abc import Callable


class _GeneratorContext:
    """A context manager running a generator up to its ``yield`` and then to its end."""

    def __init__(self, generator):
        self._generator = generator

    def __enter__(self):
        return next(self._generator)

    def __exit__(self, exception_type, exception, traceback) -> bool:
        if exception_type is None:
            try:
                next(self._generator)
            except StopIteration:
                pass
        return False


def contextmanager(function: Callable) -> Callable:
    """Turn a generator function yielding once into a context manager factory."""
    return lambda *args, **kwargs: _GeneratorContext(function(*args, **kwargs))

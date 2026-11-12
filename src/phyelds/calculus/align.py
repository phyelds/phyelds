"""
Alignment context manager for phyelds.

"""

from phyelds import engine


class AlignContext:
    """
    Context manager that scopes a block of code under an alignment point.

    Use it through ``align`` rather than directly:

    ```python
    with align("context_name"):
        ...
    ```

    Args:
        name: The name of the alignment point.
    """

    def __init__(self, name: str):
        self.name = name
        self._engine = None

    def __enter__(self):
        current_engine = engine.get()
        self._engine = current_engine
        current_engine.enter(self.name)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._engine.exit()

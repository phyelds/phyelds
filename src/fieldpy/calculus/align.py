"""
Alignment context manager for FieldPy.

"""

from fieldpy import engine


class AlignContext:
    def __init__(self, name: str):
        self.name = name

    def __enter__(self):
        engine.enter(self.name)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        engine.exit()

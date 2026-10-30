"""Helpers on Python syntax trees, shared by the build and the pruning."""
import ast


def dotted(node: ast.expr) -> str | None:
    """``"a.b.c"`` for the expression ``a.b.c``; ``None`` for other expressions."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return None if prefix is None else f"{prefix}.{node.attr}"
    return None


def decorator_name(decorator: ast.expr) -> str | None:
    """``"a.b"`` for ``@a.b`` and ``@a.b(...)``."""
    return dotted(decorator.func if isinstance(decorator, ast.Call) else decorator)

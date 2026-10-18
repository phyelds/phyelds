"""
Source rewriting behind ``@aggregate``: parse a function, align its branches, recompile it.

This module needs ``ast`` and ``inspect``, which MicroPython does not have: the
MicroPython bundle leaves it out and ships code that was rewritten at build time.
"""
import ast
import inspect
import os
import textwrap
from collections.abc import Callable, Mapping
from typing import Any

from phyelds.calculus.internal import AggregateTransformer

_DEBUG_AST = os.environ.get("PHYELDS_DEBUG_AST", "0").lower() in ("1", "true", "yes")

_TRANSFORMATION_CACHE = {}


def is_aggregate_decorator(node: ast.expr) -> bool:
    """True for ``@aggregate`` / ``@process`` and their qualified forms."""
    if isinstance(node, ast.Name):
        return node.id in ("aggregate", "process")
    return isinstance(node, ast.Attribute) and node.attr in ("aggregate", "process")


def _drop_applied_decorators(func_def: ast.AST) -> None:
    """
    Remove ``@aggregate`` and every decorator above it from the parsed definition.
    Python has already applied those around the ``aggregate`` wrapper: keeping them would
    apply them a second time on each call, re-evaluating their expressions in a scope
    where the caller's locals do not exist. Decorators below ``@aggregate`` are kept,
    since they are part of the function ``aggregate`` received.
    """
    decorators = getattr(func_def, "decorator_list", [])
    for index, decorator in enumerate(decorators):
        if is_aggregate_decorator(decorator):
            func_def.decorator_list = decorators[index + 1:]
            return


def _transformed_tree(func: Callable) -> ast.Module:
    """Parse ``func`` and rewrite its branches to align them."""
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    _drop_applied_decorators(tree.body[0])
    tree = AggregateTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    return tree


# pylint: disable=exec-used,broad-exception-caught
def transform_code(func: Callable, helpers: Mapping[str, Any]) -> Callable:
    """
    Transforms the code of the given function to include alignment contexts.

    Args:
        func: The function to transform.
        helpers: Names the rewritten code calls (``align_left``, ``align_right``,
            ``_aligned_branch``), added to the function's globals.

    Returns:
        The transformed function, or ``func`` itself if its source cannot be rewritten.
    """
    if func.__code__ in _TRANSFORMATION_CACHE:
        code_obj = _TRANSFORMATION_CACHE[func.__code__]
    else:
        try:
            tree = _transformed_tree(func)
            if _DEBUG_AST:
                print(f"--- Transformed code for {func.__name__} ---")
                print(ast.unparse(tree))
                print("--- End transformed code ---")
            # Compiled at the lines of the original file, so that tracebacks point to the source.
            ast.increment_lineno(tree, func.__code__.co_firstlineno - 1)
            code_obj = compile(tree, filename=func.__code__.co_filename, mode="exec")
            _TRANSFORMATION_CACHE[func.__code__] = code_obj
        except Exception as e:
            print(f"WARNING: AST transformation failed ({e}). Using original function.")
            return func
    scope = func.__globals__.copy()
    scope.update(helpers)
    if func.__closure__ and func.__code__.co_freevars:
        for name, cell in zip(func.__code__.co_freevars, func.__closure__):
            try:
                scope[name] = cell.cell_contents
            except ValueError:
                pass
    local_scope = {}
    exec(code_obj, scope, local_scope)
    return local_scope[func.__name__]


def str_transformed_code(func: Callable) -> str | None:
    """
    Utility to print the transformed AST source for a given function.
    Useful for debugging how the AggregateTransformer rewrites ``if`` statements.
    """
    try:
        return ast.unparse(_transformed_tree(func))
    except TypeError:
        print(f"Could not retrieve source for {func}")
        return None

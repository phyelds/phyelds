"""
Source rewriting behind ``@aggregate``: parse a function, align its branches, recompile it.

This module needs ``ast`` and ``inspect``, which MicroPython does not have: the
MicroPython bundle leaves it out and ships code that was rewritten at build time.
"""
import ast
import inspect
import os
import textwrap
import types
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from phyelds.calculus.internal import AggregateTransformer

_DEBUG_AST = os.environ.get("PHYELDS_DEBUG_AST", "0").lower() in ("1", "true", "yes")

_TRANSFORMATION_CACHE = {}
# The rewritten definition runs in a factory, nested in a scope that binds its closure variables
# and the default values of the original function.
_SCOPE, _FACTORY, _DEFAULT = "__phyelds_scope__", "__phyelds_factory__", "__phyelds_default_"


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


def _function(name: str, body: list[ast.stmt]) -> ast.FunctionDef:
    """The definition of a function ``name`` without arguments, decorators or annotations."""
    no_arguments = ast.arguments(
        posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
    )
    return ast.FunctionDef(
        name=name, args=no_arguments, body=body, decorator_list=[], returns=None, type_comment=None,
        type_params=[],
    )


def _in_factory(tree: ast.Module, names: Sequence[str]) -> ast.Module:
    """
    The definition of ``tree`` returned by a factory, nested in a scope where ``names`` are
    local: the definition reads them as closure variables, and its other names as globals.
    """
    definition = tree.body[0]
    factory = _function(_FACTORY, [definition, ast.Return(ast.Name(definition.name, ast.Load()))])
    body = [factory, ast.Return(ast.Name(_FACTORY, ast.Load()))]
    if names:
        targets = [ast.Name(name, ast.Store()) for name in names]
        body.insert(0, ast.Assign(targets=targets, value=ast.Constant(None)))
    scope = _function(_SCOPE, body)
    for node in (scope, factory):
        ast.copy_location(node, definition)
    return ast.fix_missing_locations(ast.Module(body=[scope], type_ignores=[]))


def _defaults_from_closure(definition: ast.FunctionDef) -> None:
    """
    Replace the default values of ``definition`` with names: those of ``_defaults``, so that
    the definition takes the very values of the original function, evaluated once.
    """
    arguments = definition.args
    arguments.defaults = [
        ast.Name(f"{_DEFAULT}{index}", ast.Load()) for index in range(len(arguments.defaults))
    ]
    arguments.kw_defaults = [
        None if default is None else ast.Name(f"{_DEFAULT}{argument.arg}", ast.Load())
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
    ]


def _defaults(func: Callable) -> dict[str, Any]:
    """The default values of ``func``, by the names ``_defaults_from_closure`` gives them."""
    defaults = {f"{_DEFAULT}{index}": value for index, value in enumerate(func.__defaults__ or ())}
    keywords = func.__kwdefaults__ or {}
    defaults.update((f"{_DEFAULT}{name}", value) for name, value in keywords.items())
    return defaults


def _inner_code(code: types.CodeType, name: str) -> types.CodeType:
    """The code of the function ``name`` defined in ``code``."""
    return next(
        constant for constant in code.co_consts
        if isinstance(constant, types.CodeType) and constant.co_name == name
    )


def _factory_code(func: Callable, names: Sequence[str]) -> types.CodeType:
    """The code of a factory that defines ``func`` aligned, with ``names`` in its closure."""
    tree = _transformed_tree(func)
    if _DEBUG_AST:
        print(f"--- Transformed code for {func.__name__} ---")
        print(ast.unparse(tree))
        print("--- End transformed code ---")
    # Compiled at the lines of the original file, so that tracebacks point to the source.
    ast.increment_lineno(tree, func.__code__.co_firstlineno - 1)
    _defaults_from_closure(tree.body[0])
    module = compile(_in_factory(tree, names), filename=func.__code__.co_filename, mode="exec")
    return _inner_code(_inner_code(module, _SCOPE), _FACTORY)


# pylint: disable=broad-exception-caught
def transform_code(func: Callable, helpers: Mapping[str, Any]) -> Callable:
    """
    Transforms the code of the given function to include alignment contexts.

    The transformed function runs in the globals of ``func``, shares the cells of its
    closure and takes its default values, so it reads and assigns the same variables as
    ``func``, and its defaults are the same objects.

    Args:
        func: The function to transform.
        helpers: Names the rewritten code calls (``align_left``, ``align_right``,
            ``_aligned_branch``); the closure variables of ``func`` take precedence.

    Returns:
        The transformed function, or ``func`` itself if its source cannot be rewritten.
    """
    # The function whose source is rewritten: a decorator below @aggregate wraps it.
    original = inspect.unwrap(func)
    code = original.__code__
    values = {**helpers, **_defaults(original)}
    cells = {name: types.CellType(value) for name, value in values.items()}
    cells.update(zip(code.co_freevars, original.__closure__ or ()))
    if code not in _TRANSFORMATION_CACHE:
        try:
            _TRANSFORMATION_CACHE[code] = _factory_code(original, list(cells))
        except Exception as e:
            print(f"WARNING: AST transformation failed ({e}). Using original function.")
            return func
    factory_code = _TRANSFORMATION_CACHE[code]
    closure = tuple(cells[name] for name in factory_code.co_freevars)
    factory = types.FunctionType(factory_code, original.__globals__, _FACTORY, None, closure)
    return factory()  # pylint: disable=not-callable  # pylint does not infer FunctionType


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

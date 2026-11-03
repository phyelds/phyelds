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


def _owner_class(func: Callable) -> str | None:
    """The name of the innermost class whose body defines ``func``, if any."""
    scopes = func.__qualname__.split(".")[:-1]
    while scopes:
        if scopes[-1] != "<locals>":
            return scopes[-1]
        del scopes[-2:]  # a function, and the <locals> of it
    return None


class _PrivateNames(ast.NodeTransformer):
    """
    Mangle the private names of a definition as Python does in the body of the class
    ``owner``: compiled out of the class, the definition would read other names than its
    class writes.
    """

    def __init__(self, owner: str):
        self.prefix = "_" + owner.lstrip("_")

    def mangled(self, name: str) -> str:
        """``name`` as the class sees it: ``__name`` becomes ``_Owner__name``."""
        if name.startswith("__") and not name.endswith("__") and "." not in name:
            return self.prefix + name
        return name

    def _rebinding(self, name: str, node: ast.stmt) -> list[ast.stmt]:
        """
        The statements that move ``name``, bound by ``node``, to its mangled name: a nested
        ``def __f`` keeps ``__f`` as its ``__name__``, but the class binds ``_Owner__f``.
        """
        mangled = self.mangled(name)
        if mangled == name:
            return []
        rebind = ast.Assign(
            targets=[ast.Name(mangled, ast.Store())], value=ast.Name(name, ast.Load())
        )
        forget = ast.Delete(targets=[ast.Name(name, ast.Del())])
        return [ast.copy_location(rebind, node), ast.copy_location(forget, node)]

    # pylint: disable=invalid-name,missing-function-docstring  # the visitors of ast
    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self.mangled(node.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        self.generic_visit(node)
        node.attr = self.mangled(node.attr)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        self.generic_visit(node)
        node.arg = self.mangled(node.arg)
        return node

    def visit_Global(self, node: ast.Global) -> ast.Global:
        node.names = [self.mangled(name) for name in node.names]
        return node

    visit_Nonlocal = visit_Global

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        self.generic_visit(node)
        if node.name is not None:
            node.name = self.mangled(node.name)
        return node

    def visit_MatchAs(self, node: ast.MatchAs) -> ast.MatchAs:
        self.generic_visit(node)
        if node.name is not None:
            node.name = self.mangled(node.name)
        return node

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node: ast.MatchMapping) -> ast.MatchMapping:
        self.generic_visit(node)
        if node.rest is not None:
            node.rest = self.mangled(node.rest)
        return node

    def visit_Import(self, node: ast.Import) -> list[ast.stmt]:
        statements: list[ast.stmt] = [node]
        for alias in node.names:
            if alias.asname is not None:
                alias.name, alias.asname = self.mangled(alias.name), self.mangled(alias.asname)
            elif "." in alias.name:  # imports the module as it is, binds its first package
                statements += self._rebinding(alias.name.split(".")[0], node)
            else:
                alias.name = self.mangled(alias.name)
        return statements

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        if node.module is not None:
            node.module = self.mangled(node.module)
        for alias in node.names:
            alias.name = self.mangled(alias.name)
            if alias.asname is not None:
                alias.asname = self.mangled(alias.asname)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> list[ast.stmt]:
        self.generic_visit(node)
        return [node, *self._rebinding(node.name, node)]

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> list[ast.stmt]:
        body, node.body = node.body, []
        self.generic_visit(node)  # its bases and decorators are in this class
        if node.name.lstrip("_"):  # its body is in a class of its own
            inside = ast.Module(body=body, type_ignores=[])
            _PrivateNames(node.name).generic_visit(inside)
            body = inside.body
        node.body = body
        return [node, *self._rebinding(node.name, node)]


def _transformed_tree(func: Callable) -> ast.Module:
    """Parse ``func`` and rewrite its branches to align them."""
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    _drop_applied_decorators(tree.body[0])
    tree = AggregateTransformer().visit(tree)
    owner = _owner_class(inspect.unwrap(func))
    if owner is not None and owner.lstrip("_"):
        _PrivateNames(owner).generic_visit(tree.body[0])
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

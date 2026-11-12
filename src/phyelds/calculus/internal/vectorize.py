"""
The rewriting of ``@aggregate`` for vectorized engines, which run many devices at once.

A value may then hold one value per device, with no single truth value: the control flow that
depends on truth values goes through the engine, which runs each side for the devices taking
it. ``if`` statements become calls to ``_aligned_branch``, with their branches, and the code
after them, moved into local functions that take and return the local variables; conditional
expressions, ``and``, ``or``, ``not``, ``min`` and ``max`` become calls to ``_vector_*``
helpers built on ``Engine.choose``.

The ``if`` statements inside loops, ``with`` and ``try`` stay as they are: their conditions
must have a single truth value.
"""
import ast
import itertools
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from phyelds import engine
from phyelds.calculus.internal import _bound_to_its_scope, _calls_anything, _thunk

T = TypeVar("T")

_PREFIX = "__phyelds_"
# Builtins whose calls with many arguments compare them, and become choices.
REWRITABLE_BUILTINS = frozenset({"min", "max"})
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def vectorize(definition: ast.FunctionDef, builtins: Iterable[str]) -> None:
    """
    Rewrite ``definition`` in place for a vectorized engine.

    Args:
        definition: The definition of the ``@aggregate`` function.
        builtins: The names in ``REWRITABLE_BUILTINS`` that are the builtins in the module of
            the function, so that its calls to them can become choices.
    """
    expressions = _Expressions(set(builtins) - _locals(definition))
    if _suspends(definition) or isinstance(definition, ast.AsyncFunctionDef):
        expressions.visit(definition)
        return
    globals_ = _declared(definition.body, ast.Global)
    nonlocals = _declared(definition.body, ast.Nonlocal)
    parameters = _parameters(definition.args)
    state = sorted((parameters | _locals(definition)) - globals_ - nonlocals)
    blocks = _Blocks(state, expressions, [
        declaration(names=sorted(names))
        for declaration, names in ((ast.Global, globals_), (ast.Nonlocal, nonlocals)) if names
    ])
    body = blocks.rewrite(definition.body, inside=False)
    if blocks.converted:
        unbound = [name for name in state if name not in parameters]
        if unbound:  # the local functions take every local, assigned or not yet
            initial = ast.Assign(targets=[_name(name, ast.Store()) for name in unbound],
                                 value=ast.Constant(None))
            body.insert(_after_declarations(body), initial)
    definition.body = body


class _Expressions(ast.NodeTransformer):
    """Rewrite the expressions that depend on truth values into calls to the engine."""

    def __init__(self, builtins: set[str]):
        self.builtins = builtins

    # pylint: disable=invalid-name,missing-function-docstring  # the visitors of ast
    def visit_IfExp(self, node: ast.IfExp) -> ast.expr:
        self.generic_visit(node)
        branches = (node.body, node.orelse)
        if any(map(_bound_to_its_scope, branches)):
            return node
        helper = "_aligned_branch" if any(map(_calls_anything, branches)) else "_vector_choose"
        return _call(helper, [node.test, _thunk(node.body), _thunk(node.orelse)], node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        self.generic_visit(node)
        if any(map(_bound_to_its_scope, node.values[1:])):
            return node
        helper = "_vector_and" if isinstance(node.op, ast.And) else "_vector_or"
        result = node.values[-1]
        for value in reversed(node.values[:-1]):  # a and b and c: a and (b and c)
            result = _call(helper, [value, _thunk(result)], node)
        return result

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            return _call("_vector_not", [node.operand], node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        self.generic_visit(node)
        function = node.func
        if (
            isinstance(function, ast.Name)
            and function.id in self.builtins
            and len(node.args) >= 2
            and not node.keywords
            and not any(isinstance(argument, ast.Starred) for argument in node.args)
        ):
            node.func = ast.copy_location(_name(f"_vector_{function.id}"), function)
        return node


class _Blocks:
    """
    Rewrite blocks of statements so that their ``if`` statements go through the engine.

    In a local function, a block ends returning ``(done, value, state)``: whether it
    returned, what, and the local variables, for the code after it.
    """

    def __init__(
        self, state: list[str], expressions: _Expressions, declarations: list[ast.stmt]
    ):
        self.state = state
        self.expressions = expressions
        self.declarations = declarations
        self.counter = itertools.count()
        self.converted = False

    def rewrite(self, statements: list[ast.stmt], *, inside: bool) -> list[ast.stmt]:
        """``statements``, rewritten; ``inside`` a local function, or the function itself."""
        rewritten: list[ast.stmt] = []
        for index, statement in enumerate(statements):
            if isinstance(statement, ast.If):
                return rewritten + self._if(statement, statements[index + 1:], inside=inside)
            statement = self.expressions.visit(statement)
            if inside:
                statement = _Returns(self).visit(statement)
            rewritten.append(statement)
            if isinstance(statement, ast.Return):
                return rewritten  # what follows never runs
        if inside:
            rewritten.append(ast.Return(self.outcome(ast.Constant(False), ast.Constant(None))))
        return rewritten

    def outcome(self, done: ast.expr, value: ast.expr) -> ast.Tuple:
        """The tuple a local function returns: ``(done, value, state)``."""
        return ast.Tuple(elts=[done, value, self._state(ast.Load())], ctx=ast.Load())

    def _if(self, statement: ast.If, rest: list[ast.stmt], *, inside: bool) -> list[ast.stmt]:
        """An ``if`` statement and the code after it, through the engine."""
        self.converted = True
        uid = next(self.counter)
        done, value = f"{_PREFIX}done_{uid}", f"{_PREFIX}value_{uid}"
        left, right = f"{_PREFIX}left_{uid}", f"{_PREFIX}right_{uid}"
        rewritten: list[ast.stmt] = [
            self._local_function(left, statement.body),
            self._local_function(right, statement.orelse or [ast.Pass()]),
            self._assign_outcome(done, value, _call("_aligned_branch", [
                self.expressions.visit(statement.test), self._calling(left), self._calling(right)
            ], statement)),
        ]
        if rest:
            after = f"{_PREFIX}after_{uid}"
            keep = _thunk(self.outcome(_name(done), _name(value)))
            rewritten += [
                self._local_function(after, rest),
                self._assign_outcome(done, value, _call(
                    "_vector_choose", [_name(done), keep, self._calling(after)], statement
                )),
            ]
        result = self.outcome(_name(done), _name(value)) if inside else _name(value)
        rewritten.append(ast.Return(result))
        return [ast.copy_location(node, statement) for node in rewritten]

    def _local_function(self, name: str, body: list[ast.stmt]) -> ast.FunctionDef:
        """A local function ``name`` taking the local variables, running ``body``."""
        # The local function binds the names of the function it comes from, as it does.
        declarations = [type(node)(names=list(node.names)) for node in self.declarations]
        arguments = ast.arguments(
            posonlyargs=[], args=[ast.arg(arg=name) for name in self.state], vararg=None,
            kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[],
        )
        return ast.FunctionDef(
            name=name, args=arguments, body=declarations + self.rewrite(body, inside=True),
            decorator_list=[], returns=None, type_comment=None, type_params=[],
        )

    def _calling(self, function: str) -> ast.Lambda:
        """A lambda calling the local function ``function`` with the local variables."""
        state = [_name(name) for name in self.state]
        return _thunk(ast.Call(func=_name(function), args=state, keywords=[]))

    def _assign_outcome(self, done: str, value: str, call: ast.expr) -> ast.Assign:
        """``done, value, state = call``."""
        target = ast.Tuple(
            elts=[_name(done, ast.Store()), _name(value, ast.Store()), self._state(ast.Store())],
            ctx=ast.Store(),
        )
        return ast.Assign(targets=[target], value=call)

    def _state(self, ctx: ast.expr_context) -> ast.expr:
        """The local variables, as a tuple; a name to ignore when there are none."""
        if not self.state and isinstance(ctx, ast.Store):
            return _name(f"{_PREFIX}none", ctx)
        return ast.Tuple(elts=[_name(name, ctx) for name in self.state], ctx=ctx)


class _Returns(ast.NodeTransformer):
    """Turn the ``return`` statements of a local function into its outcomes."""

    def __init__(self, blocks: _Blocks):
        self.blocks = blocks

    # pylint: disable=invalid-name,missing-function-docstring  # the visitors of ast
    def visit_Return(self, node: ast.Return) -> ast.Return:
        value = node.value if node.value is not None else ast.Constant(None)
        return ast.copy_location(ast.Return(self.blocks.outcome(ast.Constant(True), value)), node)

    def visit_FunctionDef(self, node: ast.AST) -> ast.AST:
        return node  # its returns are its own

    visit_AsyncFunctionDef = visit_ClassDef = visit_Lambda = visit_FunctionDef


def _call(function: str, arguments: list[ast.expr], where: ast.AST) -> ast.Call:
    """A call to ``function`` with ``arguments``, at the location of ``where``."""
    return ast.copy_location(ast.Call(func=_name(function), args=arguments, keywords=[]), where)


def _name(name: str, ctx: ast.expr_context | None = None) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Load() if ctx is None else ctx)


def _parameters(arguments: ast.arguments) -> set[str]:
    """The names of the parameters of a function."""
    names = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    names += [argument for argument in (arguments.vararg, arguments.kwarg) if argument]
    return {argument.arg for argument in names}


def _locals(definition: ast.FunctionDef) -> set[str]:
    """The names the body of ``definition`` binds, outside the scopes nested in it."""
    names: set[str] = set()
    for node in _walk_scope(definition.body):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def _declared(body: list[ast.stmt], kind: type) -> set[str]:
    """The names a body declares with ``kind``: ``ast.Global`` or ``ast.Nonlocal``."""
    return {name for node in _walk_scope(body) if isinstance(node, kind) for name in node.names}


def _suspends(definition: ast.FunctionDef) -> bool:
    """Whether ``definition`` yields or awaits: its blocks cannot move into functions."""
    return any(
        isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await))
        for node in _walk_scope(definition.body)
    )


def _walk_scope(body: list[ast.stmt]) -> Iterable[ast.AST]:
    """The nodes of ``body``, not entering the functions, classes and lambdas in it."""
    pending: list[ast.AST] = list(body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, _SCOPES):
            continue
        pending.extend(ast.iter_child_nodes(node))


def _after_declarations(body: list[ast.stmt]) -> int:
    """Where the first statement after the docstring and the declarations of ``body`` is."""
    index = 0
    while index < len(body) and (
        isinstance(body[index], (ast.Global, ast.Nonlocal))
        or (index == 0 and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str))
    ):
        index += 1
    return index


# What the rewritten code calls, besides _aligned_branch: choices through the engine.


def _vector_choose(condition: Any, if_true: Callable[[], T], if_false: Callable[[], T]) -> T:
    """``if_true()`` if ``condition`` else ``if_false()``, through the engine."""
    return engine.get().choose(condition, if_true, if_false)


def _vector_and(first: Any, rest: Callable[[], T]) -> Any:
    """``first and rest()``, through the engine."""
    return engine.get().choose(first, rest, lambda: first)


def _vector_or(first: Any, rest: Callable[[], T]) -> Any:
    """``first or rest()``, through the engine."""
    return engine.get().choose(first, lambda: first, rest)


def _vector_not(value: Any) -> Any:
    """``not value``, through the engine."""
    return engine.get().choose(value, lambda: False, lambda: True)


def _vector_max(first: Any, *others: Any) -> Any:
    """``max(first, *others)``, through the engine: the first of the greatest."""
    result = first
    for other in others:
        result = engine.get().choose(
            other > result, lambda other=other: other, lambda result=result: result
        )
    return result


def _vector_min(first: Any, *others: Any) -> Any:
    """``min(first, *others)``, through the engine: the first of the least."""
    result = first
    for other in others:
        result = engine.get().choose(
            other < result, lambda other=other: other, lambda result=result: result
        )
    return result


HELPERS: dict[str, Callable[..., Any]] = {
    "_vector_choose": _vector_choose,
    "_vector_and": _vector_and,
    "_vector_or": _vector_or,
    "_vector_not": _vector_not,
    "_vector_max": _vector_max,
    "_vector_min": _vector_min,
}
"""The functions the rewritten code calls, by the names it calls them."""

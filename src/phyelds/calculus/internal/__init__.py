"""
Core operations for support alignment in phyelds.
"""
import ast
from collections.abc import Sequence
import warnings


class AggregateTransformer(ast.NodeTransformer):
    # pylint: disable=missing-docstring,invalid-name
    """
    Internal transformer able to take code with if and align explicitly
    """

    def visit_FunctionDef(self, node):
        _warn_remember_with_neighbors(node.body)
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node):
        self.generic_visit(node)

        # pylint: disable=invalid-name
        def __prepare_call(name: str):
            return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[], keywords=[])

        left_call = __prepare_call("align_left")
        node.body = [
            ast.With(
                items=[ast.withitem(context_expr=left_call, optional_vars=None)],
                body=node.body
            )
        ]

        if node.orelse:
            right_call = __prepare_call("align_right")
            node.orelse = [
                ast.With(
                    items=[ast.withitem(context_expr=right_call, optional_vars=None)],
                    body=node.orelse
                )
            ]
        else:
            right_call = __prepare_call("align_right")
            node.orelse = [
                ast.With(
                    items=[ast.withitem(context_expr=right_call, optional_vars=None)],
                    body=[ast.Pass()]
                )
            ]
        return node

    def visit_IfExp(self, node):
        self.generic_visit(node)
        branches = (node.body, node.orelse)
        # Branches without calls cannot communicate: there is nothing to align. Branches
        # bound to their scope would change meaning once moved into lambdas.
        if not any(map(_calls_anything, branches)) or any(map(_bound_to_its_scope, branches)):
            return node
        # `with` cannot appear in an expression: the branches become lambdas, and
        # _aligned_branch runs the chosen one in align_left or align_right.
        call = ast.Call(
            func=ast.Name(id="_aligned_branch", ctx=ast.Load()),
            args=[node.test, _thunk(node.body), _thunk(node.orelse)],
            keywords=[],
        )
        return ast.copy_location(call, node)


def _calls_anything(expression: ast.expr) -> bool:
    """True when ``expression`` contains a call, the only way to reach neighbors or state."""
    return any(isinstance(child, ast.Call) for child in ast.walk(expression))


def _bound_to_its_scope(expression: ast.expr) -> bool:
    """
    True when ``expression`` would change meaning inside a lambda: ``:=`` would bind
    a variable of the lambda, ``yield`` and ``await`` would act on the lambda.
    """
    scoped = (ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await)
    return any(isinstance(child, scoped) for child in ast.walk(expression))


def _thunk(expression: ast.expr) -> ast.Lambda:
    """A lambda without arguments that returns ``expression``."""
    no_arguments = ast.arguments(
        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
    )
    return ast.copy_location(ast.Lambda(args=no_arguments, body=expression), expression)


def _is_named_call(call: ast.Call, name: str) -> bool:
    """True when ``call`` invokes ``name`` or ``*.name``."""
    func = call.func
    return (
        (isinstance(func, ast.Name) and func.id == name)
        or (isinstance(func, ast.Attribute) and func.attr == name)
    )


def _remember_unpacking(stmt: ast.stmt) -> tuple[str, str] | None:
    """Return the two variable names if ``stmt`` unpacks a ``remember(...)`` call."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        target, value = stmt.targets[0], stmt.value
    elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        target, value = stmt.target, stmt.value
    else:
        return None
    if not (isinstance(value, ast.Call) and _is_named_call(value, "remember")):
        return None
    if not (isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 2):
        return None
    first, second = target.elts
    if isinstance(first, ast.Name) and isinstance(second, ast.Name):
        if first.id != "_" and second.id != "_":
            return first.id, second.id
    return None


def _child_blocks(stmt: ast.stmt) -> list[Sequence[ast.stmt]]:
    """Nested statement lists of a compound statement (excluding nested definitions)."""
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []
    blocks: list[Sequence[ast.stmt]] = []
    for attr in ("body", "orelse", "finalbody"):
        block = getattr(stmt, attr, None)
        if isinstance(block, list):
            blocks.append(block)
    for handler in getattr(stmt, "handlers", ()):
        blocks.append(handler.body)
    for case in getattr(stmt, "cases", ()):
        blocks.append(case.body)
    return blocks


def _statement_expressions(stmt: ast.stmt) -> list[ast.AST]:
    """Expressions evaluated directly by ``stmt`` (excluding nested statement blocks)."""
    if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return [stmt.value] if stmt.value is not None else []
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [item.context_expr for item in stmt.items]
    if isinstance(stmt, (ast.Return, ast.Expr)):
        return [stmt.value] if stmt.value is not None else []
    return []


def _scan_expression_calls(
    expr: ast.AST,
    rebound: set[str],
    shared_stale: set[str],
    updated: set[str],
) -> None:
    """Record calls to setters and ``neighbors(...)`` uses inside ``expr``."""
    for node in ast.walk(expr):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            updated.add(node.func.id)
        if _is_named_call(node, "neighbors"):
            loaded = {
                child.id
                for arg in [*node.args, *(kw.value for kw in node.keywords)]
                for child in ast.walk(arg)
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
            }
            shared_stale.update(loaded - rebound)


def _stored_names(stmt: ast.Assign | ast.AnnAssign | ast.AugAssign) -> set[str]:
    """Variable names bound by an assignment statement."""
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
    return {
        child.id
        for target in targets
        for child in ast.walk(target)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
    }


def _warn_remember_with_neighbors(body: Sequence[ast.stmt]) -> None:
    """Warn when a ``remember`` state is passed to ``neighbors`` and updated in the same scope."""
    pairs: list[tuple[str, str]] = []
    rebound: set[str] = set()
    shared_stale: set[str] = set()
    updated: set[str] = set()

    def scan(statements: Sequence[ast.stmt]) -> None:
        for stmt in statements:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for expr in _statement_expressions(stmt):
                _scan_expression_calls(expr, rebound, shared_stale, updated)
            unpacked = _remember_unpacking(stmt)
            if unpacked is not None:
                first, second = unpacked
                pairs.extend(((first, second), (second, first)))
                rebound.discard(first)
                rebound.discard(second)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                rebound.update(_stored_names(stmt))
            for block in _child_blocks(stmt):
                scan(block)

    scan(body)
    for state_name, setter_name in pairs:
        if state_name in shared_stale and setter_name in updated:
            warnings.warn(
                f"'{state_name}' from remember() is passed to neighbors() and updated with "
                f"'{setter_name}()', which introduces a 1-round delay; use exchange() instead.",
                UserWarning,
                stacklevel=2,
            )

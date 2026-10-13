"""
Core operations for support alignment in phyelds.
"""
import ast


class AggregateTransformer(ast.NodeTransformer):
    # pylint: disable=missing-docstring,invalid-name
    """
    Internal transformer able to take code with if and align explicitly
    """

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

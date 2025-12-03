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
        return node

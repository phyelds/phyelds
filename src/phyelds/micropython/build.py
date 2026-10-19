"""
Build a copy of phyelds, and of the programs using it, that MicroPython can run.

MicroPython cannot rewrite ``@aggregate`` functions at run time (it has no ``ast`` nor
``inspect``) and lacks part of the standard library. The build runs on CPython and does
that work ahead of time, on the source:

* aligns the branches of ``@aggregate`` functions, as ``@aggregate`` would at run time;
* removes annotations, and the ``Generic[...]`` base classes;
* imports the modules MicroPython lacks from the stand-ins in ``phyelds._mpy``;
* writes down what MicroPython cannot find out by itself: the fields of dataclasses, the
  members of enums, and the parameters of the functions of the programs.
"""
import ast
from collections.abc import Sequence
from pathlib import Path

import phyelds
from phyelds.calculus.internal import AggregateTransformer
from phyelds.calculus.internal.transform import is_aggregate_decorator

_SHIMMED = {
    "abc": "abc",
    "collections.abc": "typing",
    "contextlib": "contextlib",
    "contextvars": "contextvars",
    "dataclasses": "dataclasses",
    "enum": "enum",
    "functools": "functools",
    "inspect": "inspect",
    "typing": "typing",
    "wrapt": "wrapt",
}
_TYPING = ("typing", "collections.abc")
_LEFT_OUT = ("micropython", "calculus/internal/transform.py")
_HELPERS = ("_aligned_branch", "align_left", "align_right")


def build(sources: Sequence[Path], out_dir: Path) -> None:
    """
    Write phyelds and ``sources``, rewritten for MicroPython, into ``out_dir``.

    Copy the content of ``out_dir`` to the root of the board (e.g. with
    ``mpremote cp -r out_dir/. :``).

    Args:
        sources: The modules of the program, written next to the ``phyelds`` package.
        out_dir: Where to write; created if missing.
    """
    package = Path(phyelds.__file__).parent
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package)
        if not relative.as_posix().startswith(_LEFT_OUT):
            _write(out_dir / "phyelds" / relative, transpile(path.read_text()))
    for source in sources:
        _write(out_dir / source.name, transpile(source.read_text(), signatures=True))


def transpile(source: str, *, signatures: bool = False) -> str:
    """
    Rewrite the source of a module for MicroPython.

    Args:
        source: Python source of the module.
        signatures: Record the parameters of the functions defined at the top of the
            module, which phyelds inspects when they are given as accumulations or
            processes. Meant for programs: the library does not need it.

    Returns:
        The rewritten source.
    """
    tree = ast.parse(source)
    portable = _Portable()
    tree = portable.visit(tree)
    imports = []
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if portable.aligned and not defined & set(_HELPERS):
        imports.append(f"from phyelds.calculus import {', '.join(_HELPERS)}")
    if portable.enums:
        imports.append("from phyelds._mpy.enum import members as _phyelds_enum_members")
    if signatures:
        imports.append("from phyelds._mpy.inspect import register as _phyelds_signature")
        tree.body = [statement for node in tree.body for statement in _with_signature(node)]
    tree.body[_first_statement(tree.body):0] = [ast.parse(line).body[0] for line in imports]
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


class _Portable(ast.NodeTransformer):
    # pylint: disable=missing-docstring,invalid-name
    """Rewrites a module for MicroPython; see the module docstring."""

    def __init__(self):
        self.aligned = False
        self.enums = False
        self.typing_names = set()

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias in node.names:
            if alias.name in _SHIMMED:
                alias.asname = alias.asname or alias.name
                alias.name = f"phyelds._mpy.{_SHIMMED[alias.name]}"
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        if node.module in _TYPING:
            self.typing_names.update(alias.asname or alias.name for alias in node.names)
        if node.module in _SHIMMED:
            node.module = f"phyelds._mpy.{_SHIMMED[node.module]}"
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        aggregate = any(map(is_aggregate_decorator, node.decorator_list))
        if aggregate and not getattr(node, "aligned", False):
            # At run time each @aggregate function rewrites its own original source,
            # once: the nested ones must not be rewritten again here.
            for nested in ast.walk(node):
                nested.aligned = True
            node.body = [AggregateTransformer().visit(statement) for statement in node.body]
            self.aligned = True
        node.returns = None
        self.generic_visit(node)
        node.body = node.body or [ast.Pass()]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.Assign | None:
        if node.value is None:
            return None
        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        # Type expressions are evaluated at run time in aliases, and MicroPython cannot
        # subscript classes nor combine them with |: the typing name alone stands for them.
        if self._is_typing_name(node.value):
            return node.value
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.expr:
        if self._is_typing_name(node.func) and node.func.id == "cast":
            return self.visit(node.args[1])
        return self.generic_visit(node)

    def _is_typing_name(self, node: ast.expr) -> bool:
        return isinstance(node, ast.Name) and node.id in self.typing_names

    def visit_Tuple(self, node: ast.Tuple) -> ast.expr:
        self.generic_visit(node)
        return _without_unpacking(node, "tuple")

    def visit_List(self, node: ast.List) -> ast.expr:
        self.generic_visit(node)
        return _without_unpacking(node, "list")

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        fields = [
            statement.target.id
            for statement in node.body
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
        ]
        node.bases = [base for base in node.bases if not isinstance(base, ast.Subscript)]
        if any(isinstance(base, ast.Name) and base.id == "Enum" for base in node.bases):
            node.decorator_list.append(ast.Name(id="_phyelds_enum_members", ctx=ast.Load()))
            self.enums = True
        self.generic_visit(node)
        if any(_names(decorator, "dataclass") for decorator in node.decorator_list):
            declaration = ast.parse(f"__dataclass_fields__ = {tuple(fields)!r}").body[0]
            node.body.insert(_first_statement(node.body), declaration)
        node.body = node.body or [ast.Pass()]
        return node


def _without_unpacking(node: ast.Tuple | ast.List, kind: str) -> ast.expr:
    """
    ``(*a, b)`` as ``tuple(a) + (b,)``, which MicroPython can compile; ``kind`` is
    ``"tuple"`` or ``"list"``. Unpacking assignments are left alone.
    """
    unpacks = any(isinstance(element, ast.Starred) for element in node.elts)
    if not unpacks or not isinstance(node.ctx, ast.Load):
        return node
    parts, plain = [], []
    for element in node.elts + [None]:
        if not isinstance(element, ast.Starred) and element is not None:
            plain.append(element)
            continue
        if plain:
            parts.append(type(node)(elts=plain, ctx=ast.Load()))
            plain = []
        if element is not None:
            conversion = ast.Name(id=kind, ctx=ast.Load())
            parts.append(ast.Call(func=conversion, args=[element.value], keywords=[]))
    concatenation = parts[0]
    for part in parts[1:]:
        concatenation = ast.BinOp(left=concatenation, op=ast.Add(), right=part)
    return ast.copy_location(concatenation, node)


def _names(decorator: ast.expr, name: str) -> bool:
    """True for ``@name`` and ``@name(...)``."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return isinstance(decorator, ast.Name) and decorator.id == name


def _first_statement(body: list[ast.stmt]) -> int:
    """Index after the docstring and the ``__future__`` imports of ``body``."""
    index = 0
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        index = 1
    while index < len(body) and _is_future_import(body[index]):
        index += 1
    return index


def _is_future_import(statement: ast.stmt) -> bool:
    """True for ``from __future__ import ...``."""
    return isinstance(statement, ast.ImportFrom) and statement.module == "__future__"


def _with_signature(node: ast.stmt) -> list[ast.stmt]:
    """``node``, followed by the record of its parameters if it is a function."""
    if not isinstance(node, ast.FunctionDef):
        return [node]
    record = ast.parse(f"_phyelds_signature({node.name}, {_parameters(node.args)!r})")
    return [node, record.body[0]]


def _parameters(arguments: ast.arguments) -> tuple[tuple[str, int, bool], ...]:
    """
    ``(name, kind, has_default)`` for each parameter, ``kind`` numbered as the
    ``inspect.Parameter`` kinds: positional-only, positional-or-keyword, ``*args``,
    keyword-only, ``**kwargs``.
    """
    positional = arguments.posonlyargs + arguments.args
    first_default = len(positional) - len(arguments.defaults)
    parameters = [
        (argument.arg, 0 if argument in arguments.posonlyargs else 1, index >= first_default)
        for index, argument in enumerate(positional)
    ]
    if arguments.vararg:
        parameters.append((arguments.vararg.arg, 2, False))
    parameters += [
        (argument.arg, 3, default is not None)
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
    ]
    if arguments.kwarg:
        parameters.append((arguments.kwarg.arg, 4, False))
    return tuple(parameters)


def _write(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

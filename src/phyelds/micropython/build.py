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
import modulefinder
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
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
_LEFT_OUT = ("micropython", "calculus/internal")
_HELPERS = ("_aligned_branch", "align_left", "align_right")


def build(
    sources: Sequence[Path],
    out_dir: Path,
    *,
    include: Sequence[str] = (),
    mpy: bool = False,
    optimize: int = 0,
) -> None:
    """
    Write ``sources`` and the modules of phyelds they import, rewritten for MicroPython,
    into ``out_dir``.

    The imports are found by reading the sources, not by running them: modules imported by
    a computed name go in ``include``. Without sources nor ``include``, the whole library
    is written. Docstrings are left out. Copy the content of ``out_dir`` to the root of the
    board (e.g. with ``mpremote cp -r out_dir/. :``).

    Args:
        sources: The modules of the program, written next to the ``phyelds`` package.
        out_dir: Where to write; created if missing.
        include: More modules of phyelds to write, with the modules they import, by name
            (e.g. ``"phyelds.libraries.gossip"``).
        mpy: Compile the modules of phyelds to ``.mpy`` files with ``mpy-cross``, which
            must be on the PATH, in the version of the MicroPython of the board. The board
            then does not compile them, which takes memory. The sources stay ``.py``.
        optimize: The optimization level of ``mpy-cross``, from 0 to 3; 3 leaves out the
            line numbers of tracebacks, for smaller files.

    Raises:
        ImportError: If a module in ``include`` does not exist.
        FileNotFoundError: If ``mpy`` is set and ``mpy-cross`` is not on the PATH.
    """
    mpy_cross = shutil.which("mpy-cross") if mpy else None
    if mpy and mpy_cross is None:
        raise FileNotFoundError(
            "mpy-cross is not on the PATH: install the version of the MicroPython of the board, "
            "e.g. pip install \"mpy-cross==1.29.*\""
        )
    library = _library()
    programs = {
        source.name: transpile(source.read_text(), signatures=True, docstrings=False)
        for source in sources
    }
    if programs or include:
        library = {path: library[path] for path in _imported(library, programs, include)}
    for relative, content in library.items():
        if mpy_cross:
            _compile([mpy_cross, f"-O{optimize}"], content, out_dir, Path("phyelds") / relative)
        else:
            _write(out_dir / "phyelds" / relative, content)
    for name, content in programs.items():
        _write(out_dir / name, content)


def transpile(source: str, *, signatures: bool = False, docstrings: bool = True) -> str:
    """
    Rewrite the source of a module for MicroPython.

    Args:
        source: Python source of the module.
        signatures: Record the parameters of the functions defined at the top of the
            module, which phyelds inspects when they are given as accumulations or
            processes. Meant for programs: the library does not need it.
        docstrings: Keep the docstrings. MicroPython ignores them, but they take memory
            while it compiles the module.

    Returns:
        The rewritten source.
    """
    tree = ast.parse(source)
    if not docstrings:
        _drop_docstrings(tree)
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
    _drop_unused_stand_ins(tree)
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
        value = self.visit(node.value)
        return ast.copy_location(ast.Assign(targets=[node.target], value=value), node)

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


def _library() -> dict[Path, str]:
    """The modules of phyelds that MicroPython can run, rewritten, by path in the package."""
    package = Path(phyelds.__file__).parent
    modules = {}
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package)
        if not relative.as_posix().startswith(_LEFT_OUT):
            modules[relative] = transpile(path.read_text(), docstrings=False)
    return modules


def _imported(
    library: Mapping[Path, str], programs: Mapping[str, str], include: Sequence[str]
) -> set[Path]:
    """The modules of ``library`` that ``programs`` and ``include`` import, directly or not."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for relative, content in library.items():
            _write(root / "phyelds" / relative, content)
        for name, content in programs.items():
            _write(root / name, content)
        finder = modulefinder.ModuleFinder(path=[scratch])
        for name in programs:
            finder.run_script(str(root / name))
        for name in include:
            finder.import_hook(name)
    package = root / "phyelds"
    files = [Path(module.__file__) for module in finder.modules.values() if module.__file__]
    return {file.relative_to(package) for file in files if file.is_relative_to(package)}


def _drop_unused_stand_ins(tree: ast.Module) -> None:
    """
    Remove the names that ``tree`` imports from the stand-ins and does not use, as the
    rewriting leaves many: each one takes memory on the board.
    """
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    body = []
    for statement in tree.body:
        if _imports_stand_in(statement):
            statement.names = [
                alias for alias in statement.names if (alias.asname or alias.name) in used
            ]
            if not statement.names:
                continue
        body.append(statement)
    tree.body = body


def _imports_stand_in(statement: ast.stmt) -> bool:
    """True for an import from ``phyelds._mpy``, whose modules have no side effects."""
    if isinstance(statement, ast.ImportFrom):
        return (statement.module or "").startswith("phyelds._mpy.")
    if isinstance(statement, ast.Import):
        return all(
            alias.name.startswith("phyelds._mpy.") and alias.asname for alias in statement.names
        )
    return False


def _drop_docstrings(tree: ast.Module) -> None:
    """Remove the docstrings of the module, classes and functions of ``tree``."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and _is_docstring(node.body[0]):
                node.body = node.body[1:] or ([] if isinstance(node, ast.Module) else [ast.Pass()])


def _is_docstring(statement: ast.stmt) -> bool:
    """True for a statement made of a string alone."""
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )


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
    index = 1 if body and _is_docstring(body[0]) else 0
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


def _compile(mpy_cross: list[str], content: str, out_dir: Path, relative: Path) -> None:
    """
    Compile the module ``content`` with the ``mpy_cross`` command to ``out_dir / relative``,
    as a ``.mpy`` file named ``relative`` in tracebacks; create its directory.
    """
    target = (out_dir / relative).with_suffix(".mpy")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete_on_close=False) as source:
        source.write(content)
        source.close()
        command = [*mpy_cross, "-s", relative.as_posix(), "-o", target, source.name]
        subprocess.run(command, check=True)


def _write(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, creating its directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

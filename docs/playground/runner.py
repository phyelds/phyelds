"""
Run a program written in the playground and collect what it produced.

The playground loads this module into Pyodide; it is plain Python, so it is
tested with pytest like the rest of the documentation examples.
"""
import ast
import contextlib
import io
import itertools
import runpy
import shutil
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from matplotlib import pyplot as plt

PRODUCED_SUFFIXES = (".gif", ".png")
WATCH = "__watch__"  # what records the watched values, in the globals of the program
LONGEST_LABEL = 40  # characters of the name of a watch
NOT_WATCHABLE = "Select an expression inside a function, or a line that assigns, returns or tests one."


@dataclass
class Watch:
    """An expression of the program whose value every device records: where it is, and its name."""

    start: int
    end: int
    label: str


def instrument(code: str, selections: Sequence[tuple[int, int]]) -> tuple[str, list[Watch]]:
    """
    Make the program record the value of the expression under each selection.

    A selection is a pair of offsets in UTF-16 units, as the editor counts them; an
    empty one is the caret. It watches the innermost expression around it, the value
    of an assignment, return or expression statement, or the condition of an ``if``
    or a ``while``. The k-th watched expression ``e`` becomes ``__watch__[k, (e)]``,
    on the same lines: a subscript and not a call, because @aggregate aligns apart
    the branches of ``a if c else b`` only when they call something, and moving them
    into an alignment would change the alignment of everything after them.

    Args:
        code: the program.
        selections: what to watch.

    Returns:
        The program with its watched expressions wrapped, and the watches in the
        order of the selections, at their offsets in UTF-16 units.

    Raises:
        SyntaxError: if the program does not compile.
        ValueError: if a selection is not inside the body of a function, or is not
            an expression nor one of the statements above.
    """
    source = _Source(code)
    spans = []
    watches = []
    for selection in selections:
        start, end = _trimmed(code, *(source.index(offset) for offset in selection))
        expression, label = _watched(source, _path(source, source.tree, start, end), end)
        span = source.span(expression)
        try:
            compile(_wrap(code, [span]), "<watch>", "exec")
        except SyntaxError as error:
            raise ValueError(f"{label} cannot be watched. {NOT_WATCHABLE}") from error
        spans.append(span)
        watches.append(Watch(source.utf16(span[0]), source.utf16(span[1]), label))
    return _wrap(code, spans), watches


class _Source:
    """The program and its syntax tree, with the offsets of the editor, of str and of ast."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.tree = ast.parse(code)
        # Split on newlines only, as ast counts lines: splitlines also breaks at form feeds.
        self.lines = code.split("\n")
        self.starts = list(itertools.accumulate((len(line) + 1 for line in self.lines), initial=0))

    def index(self, utf16: int) -> int:
        """The index in the code of an offset in UTF-16 units."""
        return len(self.code.encode("utf-16-le")[: 2 * utf16].decode("utf-16-le", errors="ignore"))

    def utf16(self, index: int) -> int:
        """The offset in UTF-16 units of an index in the code."""
        return len(self.code[:index].encode("utf-16-le")) // 2

    def span(self, node: ast.AST) -> tuple[int, int]:
        """Where the text of ``node`` starts and ends in the code."""
        return self._index(node.lineno, node.col_offset), self._index(node.end_lineno, node.end_col_offset)

    def text(self, node: ast.AST) -> str:
        """The text of ``node``."""
        start, end = self.span(node)
        return self.code[start:end]

    def _index(self, lineno: int, column: int) -> int:
        """The index in the code of a line and a column of ast, which counts UTF-8 bytes."""
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode()[:column].decode())


def _trimmed(code: str, start: int, end: int) -> tuple[int, int]:
    """The selection without the blanks at its ends, such as the indentation of a selected line."""
    while start < end and code[start].isspace():
        start += 1
    while end > start and code[end - 1].isspace():
        end -= 1
    return start, end


def _path(source: _Source, node: ast.AST, start: int, end: int) -> list[ast.AST]:
    """The nodes from ``node`` down to the innermost one whose text contains the selection."""
    for child in ast.iter_child_nodes(node):
        if not hasattr(child, "end_lineno"):
            # Arguments and comprehensions have no position: the selection may be in their children.
            deeper = _path(source, child, start, end)
            if len(deeper) > 1:
                return [node, *deeper]
            continue
        child_start, child_end = source.span(child)
        if child_start <= start and end <= child_end:
            return [node, *_path(source, child, start, end)]
    return [node]


def _watched(source: _Source, path: list[ast.AST], end: int) -> tuple[ast.expr, str]:
    """The expression to watch for the selection that ends at ``end`` and has this path, and its label."""
    in_a_body = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and below in node.body
        for node, below in zip(path, path[1:])
    )
    if not in_a_body:
        raise ValueError(NOT_WATCHABLE)
    node, above = path[-1], path[-2]
    if _is_target(node):
        # A name being assigned: the value assigned to it.
        statement = next(each for each in reversed(path) if not _is_target(each))
        if isinstance(statement, ast.NamedExpr):
            return statement, _label(source.text(statement.target))
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            return statement.value, _label(_targets(source, statement))
        raise ValueError(NOT_WATCHABLE)
    if isinstance(node, (ast.FormattedValue, ast.JoinedStr)) or isinstance(above, ast.JoinedStr):
        # Text inside an f-string, which a wrapper would only change: the whole f-string.
        node = next(each for each in path if isinstance(each, ast.JoinedStr))
    if isinstance(node, ast.expr):
        return node, _label(source.text(node))
    if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
        return node.value, _label(_targets(source, node))
    if isinstance(node, (ast.Return, ast.Expr)) and node.value is not None:
        return node.value, _label(source.text(node.value))
    if isinstance(node, (ast.If, ast.While)) and end <= source.span(node.body[0])[0]:
        return node.test, _label(source.text(node.test))
    raise ValueError(NOT_WATCHABLE)


def _is_target(node: ast.AST) -> bool:
    """True for a name, attribute, item or tuple being assigned or deleted."""
    return isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del))


def _targets(source: _Source, statement: ast.Assign | ast.AnnAssign) -> str:
    """The names an assignment assigns, as written."""
    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    return " = ".join(source.text(target) for target in targets)


def _label(text: str) -> str:
    """``text`` on one line, shortened."""
    text = " ".join(text.split())
    return text if len(text) <= LONGEST_LABEL else f"{text[:LONGEST_LABEL - 1]}…"


def _wrap(code: str, spans: Sequence[tuple[int, int]]) -> str:
    """``code`` with the text of the k-th span written ``__watch__[k, (text)]``."""
    # At the same offset, a watch closes before another opens; the inner watch closes
    # first and the outer one opens first.
    edits = []
    for index, (start, end) in enumerate(spans):
        edits.append((start, 1, start - end, f"{WATCH}[{index}, ("))
        edits.append((end, 0, end - start, ")]"))
    edits.sort(key=lambda edit: edit[:3])
    pieces = []
    last = 0
    for offset, _, _, text in edits:
        pieces += [code[last:offset], text]
        last = offset
    return "".join(pieces) + code[last:]


@dataclass
class Output:
    """A file produced by the program."""

    name: str
    data: bytes


@dataclass
class RunResult:
    """Whether the program ended without errors, and what it produced."""

    ok: bool
    outputs: list[Output] = field(default_factory=list)


def run_user_code(code: str, run_dir: Path) -> RunResult:
    """
    Run ``code`` as ``__main__`` from a file in the empty directory ``run_dir``.

    Args:
        code: the program.
        run_dir: where the program runs; it is emptied first.

    Returns:
        The outcome of the run, the images the program saved and the figures it
        left open.
    """
    plt.close("all")
    shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    main = run_dir / "main.py"
    main.write_text(code)
    ok = True
    with contextlib.chdir(run_dir):
        try:
            runpy.run_path(str(main), run_name="__main__")
        # Any error of the program is reported to its author, like Python would.
        except Exception as error:  # pylint: disable=broad-exception-caught
            ok = False
            _print_traceback(error, main)
    return RunResult(ok=ok, outputs=_produced_files(run_dir) + _open_figures())


def _print_traceback(error: Exception, main: Path) -> None:
    """
    Print the traceback of ``error`` to stderr, from the first frame of ``main`` on.
    A program that does not compile has no such frame: only the error is printed.
    """
    frames = traceback.extract_tb(error.__traceback__)
    first = next((index for index, frame in enumerate(frames) if frame.filename == str(main)), None)
    lines = []
    if first is not None:
        lines += ["Traceback (most recent call last):\n"]
        lines += traceback.format_list(frames[first:])
    lines += traceback.format_exception_only(error)
    print("".join(lines), end="", file=sys.stderr)


def _produced_files(run_dir: Path) -> list[Output]:
    """The images in ``run_dir``, without the PNG that RenderMonitor saves next to each GIF."""
    paths = sorted(path for path in run_dir.iterdir() if path.suffix in PRODUCED_SUFFIXES)
    gifs = {path.stem for path in paths if path.suffix == ".gif"}
    return [
        Output(path.name, path.read_bytes())
        for path in paths
        if not (path.suffix == ".png" and path.stem in gifs)
    ]


def _open_figures() -> list[Output]:
    """The figures still open, as PNG images; they are closed afterwards."""
    outputs = []
    for number in plt.get_fignums():
        buffer = io.BytesIO()
        plt.figure(number).savefig(buffer, format="png")
        outputs.append(Output(f"figure-{number}.png", buffer.getvalue()))
    plt.close("all")
    return outputs

"""
Run a program written in the playground and collect what it produced.

The playground loads this module into Pyodide; it is plain Python, so it is
tested with pytest like the rest of the documentation examples.
"""
import ast
import contextlib
import heapq
import io
import itertools
import linecache
import math
import numbers
import random
import reprlib
import runpy
import shutil
import sys
import traceback
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from matplotlib import pyplot as plt

from phyelds import engine
from phyelds.data import NeighborhoodField, State
from phyelds.simulator import Node, Simulator
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import aggregate_program_runner

PRODUCED_SUFFIXES = (".gif", ".png")
WATCH = "__watch__"  # what records the watched values, in the globals of the program
LONGEST_LABEL = 40  # characters of the name of a watch
LONGEST_TEXT = 40  # characters of the text of a value
ROUND = 1.0  # simulated time between two runs of a device
NOT_WATCHABLE = "Select an expression inside a function, or a line that assigns, returns or tests one."


@dataclass
class Watch:
    """An expression of the program whose value every device records: where it is, and its name."""

    start: int
    end: int
    label: str


@dataclass
class Value:
    """What a device computed, as the page shows it: a number on a scale, NaN if it has none, and a text."""

    number: float
    text: str
    boolean: bool = False


NO_VALUE = Value(math.nan, "")


@dataclass
class Layer:
    """A field over the devices, the result of the program or a watched expression: a number and a text each."""

    numbers: list[float]
    texts: list[str]
    boolean: bool


@dataclass
class Snapshot:
    """The network at ``time``: when each device last ran (NaN before its first round), and the layers."""

    time: float
    paused: bool
    ran: list[float]
    layers: list[Layer]


@dataclass
class Loaded:
    """Whether the code was loaded, the name of the function that runs, and what it watches."""

    ok: bool
    program: str = ""
    watches: list[Watch] = field(default_factory=list)


class Playground:
    """
    The program of the page, running on the network of the page.

    The page owns the network: where the devices are, how far they hear and what they
    sense, sent with ``update``. The program is the last ``@aggregate`` function of the
    code sent with ``load``: every device runs it once per round, asynchronously, in
    an order drawn from ``seed``.

    Args:
        run_dir: where the program is written, as main.py, for @aggregate to read it.
        seed: the seed of the order in which the devices run.
    """

    def __init__(self, run_dir: Path, seed: int = 0) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        self._main = run_dir / "main.py"
        self._seed = seed
        self._random = random.Random(seed)
        self._simulator = Simulator()
        self._clock = 0.0
        self._positions: list[tuple[float, ...]] = []
        self._radius = 0.0
        self._sensors: dict[str, set[int]] = {}
        self._program: Callable[[], Any] | None = None
        self._recorder = _Recorder()
        self._watches = 0
        self._rows: dict[int, list[Value]] = {}

    def load(self, code: str, selections: Sequence[tuple[int, int]], restart: bool) -> Loaded:
        """
        Run the code and deploy its program, watching the expressions under ``selections``.

        Args:
            code: the module that defines the program.
            selections: the expressions to watch, as ``instrument`` takes them.
            restart: start every device over, rather than swap the program of the running ones.

        Returns:
            The program loaded and its watches.
        """
        source, watches = instrument(code, selections)
        self._main.write_text(source)
        linecache.clearcache()
        namespace = runpy.run_path(str(self._main), init_globals={WATCH: self._recorder}, run_name="playground")
        program = namespace[_program_name(ast.parse(code))]
        self._program, self._watches = program, len(watches)
        if restart:
            self._restart()
        else:
            # The k-th watch may now be another expression: its values come back as the devices run.
            self._rows = {node_id: row[:1] for node_id, row in self._rows.items()}
        return Loaded(True, program.__name__, watches)

    def update(
        self, positions: Sequence[Sequence[float]], radius: float, sensors: Mapping[str, Collection[int]]
    ) -> None:
        """
        Place the devices as the page has them.

        Args:
            positions: where each device is: device k at ``positions[k]``. Devices past
                the end are removed; new ones run from the next round on.
            radius: how far a device hears.
            sensors: for every sensor, the devices on which it is on.
        """
        self._positions = [tuple(position) for position in positions]
        self._radius = radius
        self._sensors = {name: set(on) for name, on in sensors.items()}
        environment = self._simulator.environment
        count = len(self._positions)
        removed = [node_id for node_id in environment.nodes if node_id >= count]
        for node_id in removed:
            environment.remove_node(node_id)
            self._rows.pop(node_id, None)
        if removed:
            # Their next rounds go too: a device added back with the same id would run twice.
            queue = self._simulator.event_queue
            queue[:] = [event for event in queue if event.args[2].id < count]
            heapq.heapify(queue)
        for node_id, position in enumerate(self._positions):
            node = environment.nodes[node_id] if node_id in environment.nodes else self._add(node_id)
            node.position = position
            node.data.update({name: node_id in on for name, on in self._sensors.items()})
        environment.set_neighborhood_function(radius_neighborhood(radius))

    def advance(self, rounds: float) -> Snapshot:
        """Run the devices for ``rounds`` rounds, if a program is loaded, and return the network."""
        if self._program is not None:
            self._clock += rounds
            self._simulator.run(self._clock)
        return self._snapshot()

    def _restart(self) -> None:
        """Every device from its first round, in the order of the previous restart."""
        self._simulator = Simulator()
        self._random = random.Random(self._seed)
        self._clock = 0.0
        self._rows = {}
        self.update(self._positions, self._radius, self._sensors)

    def _add(self, node_id: int) -> Node:
        """A new device, whose first round comes within a round from now."""
        node = self._simulator.create_node(self._positions[node_id], node_id=node_id)
        # In (0, 1]: a first round at the start of the window would fall in it with the second.
        first = self._clock + ROUND * (1.0 - self._random.random())
        self._simulator.schedule_event(
            first - self._simulator.current_time, aggregate_program_runner, self._simulator, ROUND, node, self._run
        )
        return node

    def _run(self) -> Any:
        """The program on the device that the simulator runs, recording its result and its watches."""
        self._recorder.values = {}
        result = self._program()
        node_id = engine.get().node_context.node_id
        self._rows[node_id] = [_value(result), *(self._recorder.values.get(k, NO_VALUE) for k in range(self._watches))]
        return result

    def _snapshot(self) -> Snapshot:
        """The network now."""
        count = len(self._positions)
        rows = [self._rows.get(node_id, []) for node_id in range(count)]
        layers = []
        for k in range(1 + self._watches):
            values = [row[k] if k < len(row) else NO_VALUE for row in rows]
            known = [value for value in values if value.text]
            boolean = bool(known) and all(value.boolean for value in known)
            layers.append(Layer([value.number for value in values], [value.text for value in values], boolean))
        nodes = self._simulator.environment.nodes
        ran = [nodes[node_id].data.get("time", math.nan) for node_id in range(count)]
        return Snapshot(self._clock, False, ran, layers)


class _Recorder:
    """``__watch__`` in the program: ``__watch__[k, value]`` records ``value`` as the k-th watch, and returns it."""

    def __init__(self) -> None:
        self.values: dict[int, Value] = {}

    def __getitem__(self, key: tuple[int, Any]) -> Any:
        index, value = key
        self.values[index] = _value(value)
        return value


class _Short(reprlib.Repr):
    """Short texts of values, with floats to four significant digits."""

    def repr_float(self, value: float, level: int) -> str:  # pylint: disable=unused-argument
        """A float, to four significant digits."""
        return f"{value:.4g}"


_SHORT = _Short(maxstring=LONGEST_TEXT, maxother=LONGEST_TEXT)


def _value(value: Any) -> Value:
    """How the page shows ``value``: on a scale if it is a finite number or a boolean."""
    try:
        if isinstance(value, State):
            value = value.value
        if isinstance(value, bool):
            return Value(float(value), str(value), boolean=True)
        if isinstance(value, numbers.Real):
            number = float(value)
            text = str(value) if isinstance(value, numbers.Integral) else f"{number:.4g}"
            return Value(number if math.isfinite(number) else math.nan, text)
        if isinstance(value, NeighborhoodField):
            return Value(math.nan, f"field {_SHORT.repr(value.data)}")
        return Value(math.nan, _SHORT.repr(value))
    # The program may print values whose __repr__ fails: that must not stop its round.
    except Exception:  # pylint: disable=broad-exception-caught
        return Value(math.nan, "?")


def _program_name(tree: ast.Module) -> str:
    """The name of the last function of the module decorated with @aggregate: the program."""
    names = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and any(map(_is_aggregate, node.decorator_list))
    ]
    if not names:
        raise ValueError("Define an @aggregate function: the playground runs the last one.")
    return names[-1]


def _is_aggregate(decorator: ast.expr) -> bool:
    """True for ``@aggregate`` and ``@calculus.aggregate``."""
    if isinstance(decorator, ast.Name):
        return decorator.id == "aggregate"
    return isinstance(decorator, ast.Attribute) and decorator.attr == "aggregate"


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

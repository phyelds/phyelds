"""
Run the program of the playground live, on a network that the page owns.

The page sends the network (where the devices are, how far they hear and what
they sense), the code and the expressions to watch. Every device of a phyelds
Simulator runs the last @aggregate function of the code once per round, and each
step reports what every device computed: its result and the value of every
watched expression, in its last round. A device whose program sends a velocity
moves by it from its round on, a little at a time until its next round, and each
step reports where the devices are. Every
device hears within a range of its own, which adapts to keep about NEIGHBOURS
neighbours, and each step reports the ranges too.

The playground loads this module into Pyodide; it is plain Python, so it is
tested with pytest like the rest of the documentation examples.
"""
import ast
import enum
import heapq
import inspect
import itertools
import linecache
import math
import numbers
import random
import reprlib
import runpy
import sys
import traceback
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from phyelds import engine
from phyelds.data import NeighborhoodField, State
from phyelds.experimental.swarm import Vector
from phyelds.libraries.device import velocity
from phyelds.simulator import Node, Simulator
from phyelds.simulator.neighborhood import AdaptiveRange, adaptive_range
from phyelds.simulator.runner import aggregate_program_runner

WATCH = "__watch__"  # what records the watched values, in the globals of the program
LONGEST_LABEL = 40  # characters of the name of a watch
LONGEST_TEXT = 40  # characters of the text of a value
ROUND = 1.0  # simulated time between two runs of a device
MAX_SUGGESTIONS = 40  # names the completion of the editor offers at once
MAX_SPEED = 0.15  # how far a device moves in a round at most
GLIDE = 0.1  # the time between two moves of a device: it moves smoothly, not once a round
STILL = 0.01  # a velocity slower than this on the plane has no heading: the device stands still
ARENA = 5.0  # the side of the square in which the devices move: SPAN in walkthrough/model.js
NEIGHBOURS = 8  # how many neighbours the range of a device adapts to keep
TOLERANCE = 4  # how many more or fewer are fine
RANGE_STEP = 0.05  # how much a range changes in a round
SHORTEST_RANGE = 0.3  # the ranges of the slider of the page
LONGEST_RANGE = ARENA
NOT_WATCHABLE = "Select an expression inside a function, or a line that assigns, returns or tests one."


@dataclass
class Watch:
    """An expression of the program whose value every device records: where it is, and its name."""

    start: int
    end: int
    label: str


@dataclass
class Value:
    """
    What a device computed, as the page shows it: a number on a scale, NaN if it has none,
    and a text. A direction is a vector, its number the angle from east, in degrees. A
    value whose type has a known range, as the members of an enum, has ``low`` and ``high``.
    """

    number: float
    text: str
    boolean: bool = False
    direction: bool = False
    low: float = math.nan
    high: float = math.nan


NO_VALUE = Value(math.nan, "")


@dataclass
class Layer:
    """
    A field over the devices, the result of the program or a watched expression: a number
    and a text each, whether all its values are booleans, or all directions, and the scale
    of its numbers: from ``low`` to ``high``, which only widens in a run.
    """

    numbers: list[float]
    texts: list[str]
    boolean: bool
    direction: bool = False
    low: float = math.nan
    high: float = math.nan


@dataclass
class Snapshot:
    """
    The network at ``time``: whether an error paused it, whether it is stable (in a whole
    round, no device moved nor showed anything new), when each device last ran (NaN before
    its first round), the layers, where each device is, and how far it hears.
    """

    time: float
    paused: bool
    stable: bool
    ran: list[float]
    layers: list[Layer]
    positions: list[list[float]]
    ranges: list[float]


@dataclass
class Suggestion:
    """A name that completes the code at the caret, and what it names: function, module, keyword…"""

    name: str
    kind: str


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
        self._neighbourhood: AdaptiveRange | None = None
        self._sensors: dict[str, set[int]] = {}
        self._program: Callable[[], Any] | None = None
        self._source = ""  # the code of the running program, watches included
        self._error: Exception | None = None  # what stopped the network, until the next load
        self._recorder = _Recorder()
        self._watches = 0
        self._rows: dict[int, list[Value]] = {}
        self._changed = 0.0  # when a device last moved or showed something new
        self._scales: dict[int, tuple[float, float]] = {}  # the scale of each layer, so far in this run

    def load(self, code: str, selections: Sequence[tuple[int, int]], restart: bool) -> Loaded:
        """
        Run the code and deploy its program, watching the expressions under ``selections``.

        Args:
            code: the module that defines the program.
            selections: the expressions to watch, as ``instrument`` takes them.
            restart: start every device over, rather than swap the program of the running ones.

        Returns:
            The program loaded and its watches. If the code has an error, which is
            printed to stderr, nothing is loaded and the running program goes on.
        """
        try:
            # Compiled first as it is, so that its own errors are not blamed on the watches.
            compile(code, str(self._main), "exec")
            source, watches = instrument(code, selections)
            self._write(source)
            namespace = runpy.run_path(str(self._main), init_globals={WATCH: self._recorder}, run_name="playground")
            program = _program(namespace, ast.parse(code))
        # The errors of the code are reported to its author, like Python would.
        except Exception as error:  # pylint: disable=broad-exception-caught
            _print_traceback(error, self._main)
            # @aggregate reads a function from main.py the first time it runs: it must find the running code.
            self._write(self._source)
            return Loaded(False)
        self._program, self._source, self._watches, self._error = program, source, len(watches), None
        self._scales = {}  # the k-th layer may now be another expression
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
            positions: where the page placed each device: device k at ``positions[k]``.
                A device the program moved stays where it is, unless the page placed it
                elsewhere since. Devices past the end are removed; new ones run from the
                next round on.
            radius: how far a device hears at first: its range then adapts, until
                the page changes the radius, which starts every range over.
            sensors: for every sensor, the devices on which it is on.
        """
        placed = self._positions
        self._positions = [tuple(position) for position in positions]
        self._radius = radius
        self._sensors = {name: set(on) for name, on in sensors.items()}
        environment = self._simulator.environment
        count = len(self._positions)
        removed = [node_id for node_id in environment.nodes if node_id >= count]
        for node_id in removed:
            environment.remove_node(node_id)
            self._rows.pop(node_id, None)
            if self._neighbourhood is not None:
                # A device added back starts with the radius of the page, not the range it had.
                self._neighbourhood.ranges.pop(node_id, None)
        if removed:
            # Their next rounds go too: a device added back with the same id would run twice.
            queue = self._simulator.event_queue
            queue[:] = [event for event in queue if event.args[2].id < count]
            heapq.heapify(queue)
        for node_id, position in enumerate(self._positions):
            node = environment.nodes[node_id] if node_id in environment.nodes else self._add(node_id)
            if node_id >= len(placed) or placed[node_id] != position:
                node.position = position
            node.data.update({name: node_id in on for name, on in self._sensors.items()})
        if self._neighbourhood is None or self._neighbourhood.radius != radius:
            self._neighbourhood = adaptive_range(
                radius, neighbors=NEIGHBOURS, tolerance=TOLERANCE, step=RANGE_STEP,
                min_range=SHORTEST_RANGE, max_range=LONGEST_RANGE,
            )
        environment.set_neighborhood_function(self._neighbourhood)

    def advance(self, rounds: float) -> Snapshot:
        """Run the devices for ``rounds`` rounds, unless no program runs or an error paused them."""
        if self._program is not None and self._error is None:
            self._clock += rounds
            self._simulator.run(self._clock)
        return self._snapshot()

    def _write(self, source: str) -> None:
        """Put ``source`` in main.py, where @aggregate reads the functions that it rewrites."""
        self._main.write_text(source)
        # linecache notices a new main.py by its size and time, which may both stay the same.
        linecache.clearcache()

    def _restart(self) -> None:
        """Every device from its first round, where the page placed it, in the order of the previous restart."""
        self._simulator = Simulator()
        self._random = random.Random(self._seed)
        self._clock = 0.0
        self._rows = {}
        self._changed = 0.0
        self._scales = {}
        positions, self._positions = self._positions, []
        self._neighbourhood = None
        self.update(positions, self._radius, self._sensors)

    def _add(self, node_id: int) -> Node:
        """A new device, whose first round comes within a round from now."""
        node = self._simulator.create_node(self._positions[node_id], node_id=node_id)
        # In (0, 1]: a first round at the start of the window would fall in it with the second.
        first = self._clock + ROUND * (1.0 - self._random.random())
        self._simulator.schedule_event(
            first - self._simulator.current_time, aggregate_program_runner, self._simulator, ROUND, node, self._run
        )
        self._simulator.schedule_event(first - self._simulator.current_time, self._glide, self._simulator, GLIDE, node)
        return node

    def _run(self) -> Any:
        """The program on the device that the simulator runs, recording its result and its watches."""
        self._recorder.values = {}
        try:
            result = self._program()
        # An error pauses the network, and is reported once; the round of the device ends normally,
        # so that the simulator keeps it on schedule.
        except Exception as error:  # pylint: disable=broad-exception-caught
            if self._error is None:
                self._error = error
                _print_traceback(error, self._main)
            self._simulator.stop()
            result = None
        node_id = engine.get().node_context.node_id
        row = [_value(result), *(self._recorder.values.get(k, NO_VALUE) for k in range(self._watches))]
        # Compared as shown: NaN differs from itself, and a value settling past the shown digits is settled.
        if [value.text for value in row] != [value.text for value in self._rows.get(node_id, [])]:
            self._changed = self._simulator.current_time
        self._rows[node_id] = row
        return result

    def _glide(self, simulator: Simulator, delta: float, node: Node) -> None:
        """Move ``node`` for ``delta`` by the velocity its last round sent, and again after ``delta``."""
        before = node.position
        self._move(node, velocity.read(node.data.get("outputs", {})), delta)
        if node.position != before:
            self._changed = simulator.current_time
        simulator.schedule_event(delta, self._glide, simulator, delta, node)

    @staticmethod
    def _move(node: Node, heading: Sequence[float] | None, duration: float) -> None:
        """Move ``node`` by ``heading`` for ``duration``, at MAX_SPEED at most, and inside the arena."""
        if heading is None:
            return
        step = [component * duration for component in tuple(heading)[:len(node.position)]]
        length = math.sqrt(sum(component * component for component in step))
        longest = MAX_SPEED * duration / ROUND
        scale = longest / length if length > longest else 1.0
        node.position = tuple(
            min(ARENA, max(0.0, coordinate + component * scale)) for coordinate, component in zip(node.position, step)
        )

    def _widened(self, k: int, known: Sequence[Value]) -> tuple[float, float]:
        """The scale of layer ``k``: its scale so far, widened to its values and their known ranges."""
        ends = [end for value in known for end in (value.number, value.low, value.high) if math.isfinite(end)]
        ends += [end for end in self._scales.get(k, ()) if math.isfinite(end)]
        if not ends:
            return math.nan, math.nan
        self._scales[k] = (min(ends), max(ends))
        return self._scales[k]

    def _snapshot(self) -> Snapshot:
        """The network now."""
        count = len(self._positions)
        rows = [self._rows.get(node_id, []) for node_id in range(count)]
        layers = []
        for k in range(1 + self._watches):
            values = [row[k] if k < len(row) else NO_VALUE for row in rows]
            known = [value for value in values if value.text]
            boolean = bool(known) and all(value.boolean for value in known)
            direction = bool(known) and all(value.direction for value in known)
            low, high = self._widened(k, known)
            figures, texts = [value.number for value in values], [value.text for value in values]
            layers.append(Layer(figures, texts, boolean, direction, low, high))
        nodes = self._simulator.environment.nodes
        ran = [nodes[node_id].data.get("time", math.nan) for node_id in range(count)]
        stable = self._clock - self._changed >= ROUND
        positions = [list(nodes[node_id].position) for node_id in range(count)]
        ranges = [self._neighbourhood.range_of(nodes[node_id]) for node_id in range(count)]
        return Snapshot(self._clock, self._error is not None, stable, ran, layers, positions, ranges)


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
        if isinstance(value, enum.Enum) and isinstance(value, numbers.Real):
            # A member of an IntEnum: its name, on the scale of all the members.
            members = [float(member) for member in type(value)]
            return Value(float(value), value.name, low=min(members), high=max(members))
        if isinstance(value, bool):
            return Value(float(value), str(value), boolean=True)
        if isinstance(value, numbers.Real):
            number = float(value)
            text = str(value) if isinstance(value, numbers.Integral) else f"{number:.4g}"
            return Value(number if math.isfinite(number) else math.nan, text)
        if isinstance(value, Vector):
            moving = math.sqrt(value.x * value.x + value.y * value.y) >= STILL
            angle = math.degrees(math.atan2(value.y, value.x)) if moving else math.nan
            height = f", z={value.z:.2f}" if value.z else ""
            return Value(angle, f"(x={value.x:.2f}, y={value.y:.2f}{height})", direction=True)
        if isinstance(value, NeighborhoodField):
            return Value(math.nan, f"field {_SHORT.repr(value.data)}")
        return Value(math.nan, _SHORT.repr(value))
    # The program may print values whose __repr__ fails: that must not stop its round.
    except Exception:  # pylint: disable=broad-exception-caught
        return Value(math.nan, "?")


def _program(namespace: Mapping[str, Any], tree: ast.Module) -> Callable[[], Any]:
    """The program in the ``namespace`` of the module whose syntax is ``tree``."""
    program = namespace[_program_name(tree)]
    try:
        inspect.signature(program).bind()
    except TypeError as error:
        raise ValueError(f"{program.__name__} runs on every device without arguments: {error}") from error
    return program


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
        return _index(self.code, utf16)

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


def complete(code: str, offset: int) -> list[Suggestion]:
    """
    The names that complete the code at the caret, as jedi infers them.

    Args:
        code: the program, as the editor holds it, compiling or not.
        offset: where the caret is, in UTF-16 units, as the editor counts.

    Returns:
        At most MAX_SUGGESTIONS names, the likeliest first.
    """
    # Imported here: the browser downloads jedi only for the readers who type.
    import jedi  # pylint: disable=import-outside-toplevel

    index = _index(code, offset)
    line = code.count("\n", 0, index) + 1
    column = index - (code.rfind("\n", 0, index) + 1)
    completions = jedi.Script(code).complete(line, column)
    return [Suggestion(completion.name, completion.type) for completion in completions[:MAX_SUGGESTIONS]]


def _index(code: str, utf16: int) -> int:
    """The index in ``code`` of an offset in UTF-16 units."""
    return len(code.encode("utf-16-le")[: 2 * utf16].decode("utf-16-le", errors="ignore"))


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

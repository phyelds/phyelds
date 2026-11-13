"""
A vectorized engine for the tests: it runs many devices at once, each value holding one value
per device, as a batch engine on a GPU would. It drives one ``MutableEngine`` per device in
lockstep, entering alignment points only for the devices running the code, so each device
sees the very paths, state and messages of a round on its own.
"""
import operator
from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any

from phyelds import engine
from phyelds.vm import Engine, NodeContext
from phyelds.vm.internal import MutableEngine

IDLE = object()
"""The value of a device that does not run the code that computes it."""


class Lanes:
    """One value per device; operations apply device by device, for the running ones."""

    __slots__ = ("values",)
    __hash__ = None  # type: ignore[assignment]  # == compares device by device

    def __init__(self, values):
        self.values = list(values)

    def __bool__(self):
        raise TypeError("a value per device has no single truth value")

    def __iter__(self):
        raise TypeError("a value per device cannot be iterated as one")

    def __repr__(self):
        return f"Lanes({self.values!r})"

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lane_wise(getattr, self, name)

    def __call__(self, *args, **kwargs):
        return lane_wise(lambda function, *rest, **named: function(*rest, **named),
                         self, *args, **kwargs)

    def __getitem__(self, index):
        return lane_wise(operator.getitem, self, index)


_BINARY = {
    "add": operator.add, "sub": operator.sub, "mul": operator.mul,
    "truediv": operator.truediv, "floordiv": operator.floordiv, "mod": operator.mod,
    "pow": operator.pow, "and": operator.and_, "or": operator.or_, "xor": operator.xor,
}
_COMPARISONS = {
    "lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge,
    "eq": operator.eq, "ne": operator.ne,
}
_UNARY = {"neg": operator.neg, "pos": operator.pos, "abs": operator.abs, "invert": operator.invert}

for _name, _function in _BINARY.items():
    setattr(Lanes, f"__{_name}__", lambda self, other, f=_function: lane_wise(f, self, other))
    setattr(Lanes, f"__r{_name}__",
            lambda self, other, f=_function: lane_wise(lambda a, b: f(b, a), self, other))
for _name, _function in _COMPARISONS.items():
    setattr(Lanes, f"__{_name}__", lambda self, other, f=_function: lane_wise(f, self, other))
for _name, _function in _UNARY.items():
    setattr(Lanes, f"__{_name}__", lambda self, f=_function: lane_wise(f, self))


def lane(value: Any, index: int) -> Any:
    """The value of device ``index``: its own if ``value`` is a ``Lanes``, else ``value``."""
    return value.values[index] if isinstance(value, Lanes) else value


def plain(value: Any, index: int) -> Any:
    """The value of device ``index`` in ``value``, inside tuples too."""
    if isinstance(value, tuple):
        return tuple(plain(item, index) for item in value)
    return lane(value, index)


def lane_wise(function: Callable, *args: Any, **kwargs: Any) -> Lanes:
    """``function`` of the values of each running device in ``args``; idle for the others."""
    running = engine.get().running
    return Lanes(
        function(*(lane(arg, index) for arg in args),
                 **{key: lane(arg, index) for key, arg in kwargs.items()})
        if active else IDLE
        for index, active in enumerate(running)
    )


class _LanesContext(NodeContext):
    """The context of all the devices: their ids, sensors and outputs, device by device."""

    def __init__(self, lanes_engine: "LanesEngine"):
        super().__init__(Lanes(context.node_id for context in lanes_engine.contexts))
        self._lanes = lanes_engine

    def sense(self, sensor_name):
        return lane_wise(lambda context: context.sense(sensor_name), Lanes(self._lanes.contexts))

    def store(self, output_name, value):
        lane_wise(lambda context, item: context.store(output_name, item),
                  Lanes(self._lanes.contexts), value)

    def position(self):
        return self.sense("position")

    def time(self):
        return self.sense("time")


class LanesEngine(Engine):
    """A vectorized engine running a ``MutableEngine`` per device, in lockstep."""

    vectorized = True

    def __init__(self, devices: Sequence[Hashable]):
        super().__init__()
        self.engines = [MutableEngine() for _ in devices]
        self.contexts = [NodeContext(device, {}) for device in devices]
        self.running = [True] * len(devices)

    def setup(self, node_context, messages, state=None):
        raise NotImplementedError("set the devices up with setup_devices")

    def setup_devices(
        self,
        sensors: Sequence[Mapping[str, Any]],
        inboxes: Sequence[Mapping[Hashable, Mapping[str, Any]]],
        states: Sequence[Mapping[str, Any] | None],
    ) -> "LanesEngine":
        """Prepare a round of every device, as ``Engine.setup`` does for one."""
        for index, node_engine in enumerate(self.engines):
            self.contexts[index] = NodeContext(self.contexts[index].node_id, dict(sensors[index]))
            node_engine.setup(self.contexts[index], inboxes[index], states[index])
        self.node_context = _LanesContext(self)
        return self

    def _each(self, method: str, *args: Any, **kwargs: Any) -> Lanes:
        """``method`` of the engine of each running device, with its own arguments."""
        return lane_wise(lambda node_engine, *rest, **named: getattr(node_engine, method)(*rest, **named),
                         Lanes(self.engines), *args, **kwargs)

    def enter(self, name):
        self._each("enter", name)

    def exit(self):
        self._each("exit")

    def current_path(self):
        return self._each("current_path")

    def write_state(self, value, stack=None):
        self._each("write_state", value, stack)

    def read_state(self, stack=None):
        return self._each("read_state", stack)

    def read_state_or(self, init, stack=None):
        return self._each("read_state_or", init, stack)

    def forget(self, _self_path):
        self._each("forget", _self_path)

    def send(self, data, stack=None):
        self._each("send", data, stack)

    def neighbor_field(self, local, path=None, *args, **kwargs):
        return self._each("neighbor_field", local, path, *args, **kwargs)

    def begin_process(self, name):
        return self._each("begin_process", name)

    def end_process(self, token, commit):
        self._each("end_process", token, commit)

    def branch(self, condition, if_true, if_false):
        if not isinstance(condition, Lanes):
            return super().branch(condition, if_true, if_false)
        return self._split(condition, if_true, if_false, aligned=True)

    def choose(self, condition, if_true, if_false):
        if not isinstance(condition, Lanes):
            return super().choose(condition, if_true, if_false)
        return self._split(condition, if_true, if_false, aligned=False)

    def _split(self, condition: Lanes, if_true, if_false, *, aligned: bool) -> Any:
        """Run each side for the running devices taking it, and merge what they return."""
        running = self.running
        left = [active and bool(lane(condition, index)) for index, active in enumerate(running)]
        right = [active and not taken for active, taken in zip(running, left)]
        outcomes = []
        for mask, side, name in ((left, if_true, "left"), (right, if_false, "right")):
            if not any(mask):
                outcomes.append(IDLE)
                continue
            self.running = mask
            try:
                if aligned:
                    self.enter(name)
                outcomes.append(side())
                if aligned:
                    self.exit()
            finally:
                self.running = running
        if outcomes[0] is IDLE or outcomes[1] is IDLE:  # one side ran for every device
            return outcomes[1] if outcomes[0] is IDLE else outcomes[0]
        return _merge(left, right, *outcomes)

    def finish(self) -> list[tuple[dict, dict, dict]]:
        """End the round of every device: its outbox, state and outputs."""
        return [
            (node_engine.cooldown(), node_engine.state_trace(), context.outputs)
            for node_engine, context in zip(self.engines, self.contexts)
        ]


def _merge(left_mask: list[bool], right_mask: list[bool], left: Any, right: Any) -> Any:
    """The values of ``left`` for the devices of ``left_mask``, of ``right`` for the others."""
    if isinstance(left, tuple) and isinstance(right, tuple) and len(left) == len(right):
        return tuple(_merge(left_mask, right_mask, *pair) for pair in zip(left, right))
    return Lanes(
        lane(left, index) if on_left else lane(right, index) if on_right else IDLE
        for index, (on_left, on_right) in enumerate(zip(left_mask, right_mask))
    )


def lanes_rounds(
    program: Callable[[], Any],
    sensors: Mapping[Hashable, Mapping[str, Any]],
    neighbors: Mapping[Hashable, Sequence[Hashable]],
    rounds: int,
) -> list[dict[Hashable, tuple]]:
    """
    Synchronous rounds of every device at once on a ``LanesEngine``: for each round, the
    result, outbox, state and outputs of each device.
    """
    devices = list(sensors)
    states: dict[Hashable, Any] = {}
    outboxes: dict[Hashable, Any] = {}
    history = []
    for _ in range(rounds):
        lanes = LanesEngine(devices).setup_devices(
            [sensors[device] for device in devices],
            [{other: outboxes[other] for other in neighbors[device] if other in outboxes}
             for device in devices],
            [states.get(device) for device in devices],
        )
        token = engine.set(lanes)
        try:
            result = program()
        finally:
            engine.reset(token)
        finished = lanes.finish()
        history.append({
            device: (plain(result, index), *finished[index])
            for index, device in enumerate(devices)
        })
        outboxes = {device: finished[index][0] for index, device in enumerate(devices)}
        states = {device: finished[index][1] for index, device in enumerate(devices)}
    return history

import functools

from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.device import local_id
from tests.calculus.mock import MockSimulator

SCALE = 1
COUNTER = 0


def _run(program):
    simulator = MockSimulator(1)
    simulator.cycle(program)
    return simulator.nodes[0].root


def passing(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


def test_aggregate_keeps_the_metadata_of_the_wrapped_function():
    def program():
        """Docs of the program."""
        return 1

    wrapped = aggregate(program)
    assert wrapped.__name__ == "program"
    assert wrapped.__qualname__ == program.__qualname__
    assert wrapped.__doc__ == "Docs of the program."
    assert wrapped.__wrapped__ is program


def test_aggregate_sees_a_global_rebound_after_its_first_call():
    global SCALE

    @aggregate
    def program():
        return SCALE * 10

    first = _run(program)
    SCALE = 2
    try:
        second = _run(program)
    finally:
        SCALE = 1

    assert (first, second) == (10, 20)


def test_aggregate_sees_a_closure_variable_rebound_after_its_first_call():
    factor = 1

    @aggregate
    def program():
        return factor * 10

    first = _run(program)
    factor = 2
    second = _run(program)

    assert (first, second) == (10, 20)


def test_aggregate_runs_each_function_when_they_share_a_decorator_below_it():
    @aggregate
    @passing
    def first():
        return "first"

    @aggregate
    @passing
    def second():
        return "second"

    assert (_run(first), _run(second)) == ("first", "second")


def test_aggregate_assigns_a_variable_declared_global():
    global COUNTER
    COUNTER = 0

    @aggregate
    def program():
        global COUNTER
        COUNTER += 1
        return COUNTER

    results = [_run(program) for _ in range(3)]

    assert (results, COUNTER) == ([1, 2, 3], 3)


def test_aggregate_assigns_a_variable_declared_nonlocal_and_still_aligns_its_branches():
    calls = 0
    simulator = MockSimulator(3)

    @aggregate
    def program():
        nonlocal calls
        calls += 1
        if local_id() < 2:
            return neighbors(local_id())
        else:
            return neighbors(local_id())

    simulator.cycle_for(program, 3)

    assert calls == 9
    assert simulator.nodes[2].root.data == {2: 2}


class _Base:
    def value(self):
        return 1


def test_aggregate_method_calls_super_without_arguments():
    class Child(_Base):
        @aggregate
        def value(self):
            return super().value() + 1

    assert _run(Child().value) == 2

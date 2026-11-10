import functools
import sys
import types
from dataclasses import dataclass
from typing import NamedTuple

import pytest

from phyelds import engine
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import local_id
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext, MockSimulator

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


_RECORDED = []


def recorded(fn):
    _RECORDED.append(fn.__name__)
    return fn


@pytest.fixture(autouse=True)
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))


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


def test_aggregate_keeps_the_default_values_of_the_function():
    @aggregate
    def program(first=[], *, second=[]):
        first.append(1)
        second.append(2)
        return len(first) + len(second)

    results = [_run(program) for _ in range(3)]

    assert results == [2, 4, 6]
    assert program.__wrapped__.__defaults__ == ([1, 1, 1],)
    assert program.__wrapped__.__kwdefaults__ == {"second": [2, 2, 2]}


def test_aggregate_rewrites_its_function_once_and_not_at_each_call():
    @aggregate
    @recorded
    def program():
        return 1

    _RECORDED.clear()
    results = [_run(program) for _ in range(3)]

    assert results == [1, 1, 1]
    assert _RECORDED == ["program"]


def test_aggregate_runs_a_function_without_source_as_it_is_and_warns_once(capsys):
    namespace = {"aggregate": aggregate}
    exec("@aggregate\ndef program():\n    return 1\n", namespace)

    results = [_run(namespace["program"]) for _ in range(3)]

    assert results == [1, 1, 1]
    assert capsys.readouterr().out.count("WARNING: AST transformation failed") == 1


def test_aggregate_prints_the_rewritten_code_when_debugging(monkeypatch, capsys):
    monkeypatch.setenv("PHYELDS_DEBUG_AST", "1")

    @aggregate
    def program():
        if True:
            return 1
        return 2

    _run(program)

    printed = capsys.readouterr().out
    assert "--- Transformed code for program ---" in printed
    assert "with align_left():" in printed


class _Holder:
    def __init__(self):
        self.__secret = 41

    @aggregate
    def reveal(self):
        return self.__secret + 1


def test_aggregate_method_reads_a_private_attribute_of_its_class():
    assert _run(_Holder().reveal) == 42


_Private__offset = 100  # what __offset means in the body of _Private


class _Private:
    __limit = 10

    def __init__(self):
        self.__secret = 41

    def __helper(self):
        return 1

    @aggregate
    def everything(self, __bonus=1, *, __factor=1):
        from math import floor as __floor
        __local = self.__secret + self.__helper() + __bonus + __offset  # noqa: F821 (_Private__offset)

        def __twice(__value):
            return __value * 2

        class __Box:
            __inside = 3

            def peek(self):
                return self.__inside

        try:
            raise KeyError("private")
        except KeyError as __error:
            caught = __error.args[0]
        values = [__item * __factor for __item in range(3)]
        match {"key": __floor(2.5)}:
            case {"key": __found, **__rest}:
                matched = (__found, __rest)
        return (
            __twice(__local) + self.__limit + sum(values), caught, matched,
            __twice.__name__, __Box().peek(), (__walrus := 7) + __walrus,
        )


def test_aggregate_method_sees_the_private_names_of_its_class_as_python_does():
    holder = _Private()

    for arguments in ({}, {"_Private__bonus": 2, "_Private__factor": 3}):
        expected = _Private.everything.__wrapped__(holder, **arguments)
        assert _run(lambda: holder.everything(**arguments)) == expected


_Counted__count = 0  # what __count means in the body of _Counted


class _Counted:
    @aggregate
    def bump(self):
        global __count
        __count += 1
        return __count


def test_aggregate_method_assigns_a_private_global_as_python_does():
    global _Counted__count
    _Counted__count = 0
    counted = _Counted()

    results = [_Counted.bump.__wrapped__(counted), _run(counted.bump)]

    assert (results, _Counted__count) == ([1, 2], 2)


class _Imports:
    @aggregate
    def load(self):
        import __plain
        import __aliased as __bound
        import __package.inner
        return __plain.value, __bound.value, __package.inner.value


def test_aggregate_method_imports_private_modules_as_python_does(monkeypatch):
    for name, value in (("_Imports__plain", 1), ("_Imports__aliased", 2), ("__package", 0), ("__package.inner", 3)):
        module = types.ModuleType(name)
        module.value = value
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys.modules["__package"], "inner", sys.modules["__package.inner"], raising=False)

    expected = _Imports.load.__wrapped__(_Imports())

    assert expected == (1, 2, 3)
    assert _run(_Imports().load) == expected


def test_aggregate_returns_the_plain_value_of_remember():
    @aggregate
    def program():
        return remember(42)[0]

    result = program()

    assert type(result) is int
    assert result == 42

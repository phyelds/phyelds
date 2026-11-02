from phyelds.calculus import aggregate
from tests.calculus.mock import MockSimulator

SCALE = 1


def _run(program):
    simulator = MockSimulator(1)
    simulator.cycle(program)
    return simulator.nodes[0].root


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

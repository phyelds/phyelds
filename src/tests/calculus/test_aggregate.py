from phyelds.calculus import aggregate
from tests.calculus.mock import MockSimulator


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

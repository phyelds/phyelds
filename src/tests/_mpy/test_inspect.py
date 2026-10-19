import pytest

from phyelds._mpy.inspect import Parameter, register, signature


def test_signature_returns_the_recorded_parameters_in_order():
    def step(edge, data=None):
        return data

    register(step, (("edge", 1, False), ("data", 1, True)))

    parameters = list(signature(step).parameters.values())

    assert [(p.name, p.kind) for p in parameters] == [("edge", 1), ("data", 1)]
    assert parameters[0].default is Parameter.empty
    assert parameters[1].default is not Parameter.empty


def test_signature_raises_for_functions_never_recorded():
    with pytest.raises(ValueError):
        signature(lambda value: value)

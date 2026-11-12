import operator

import pytest

from phyelds._mpy import operator as stand_in

NAMES = ["add", "sub", "mul", "truediv", "and_", "or_", "eq", "ne", "lt", "le", "gt", "ge"]


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("first, second", [(6, 3), (2.5, 4.0), (False, True)])
def test_operator_stand_in_computes_what_operator_does(name, first, second):
    if name in ("and_", "or_") and isinstance(first, float):
        pytest.skip("bitwise operators take integers and booleans")

    assert getattr(stand_in, name)(first, second) == getattr(operator, name)(first, second)

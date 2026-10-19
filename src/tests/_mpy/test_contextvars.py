import pytest

from phyelds._mpy.contextvars import ContextVar


def test_context_var_returns_the_value_set():
    variable = ContextVar("engine")

    variable.set(3)

    assert variable.get() == 3


def test_context_var_falls_back_to_defaults():
    assert ContextVar("engine", default=1).get() == 1
    assert ContextVar("engine").get(2) == 2


def test_context_var_raises_when_never_set():
    with pytest.raises(LookupError, match="engine"):
        ContextVar("engine").get()

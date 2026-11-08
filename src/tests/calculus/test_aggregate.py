import pytest

from phyelds import engine
from phyelds.calculus import aggregate, remember
from phyelds.data import State
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext


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


def test_aggregate_returns_the_value_of_a_returned_state():
    # Arrange
    @aggregate
    def program():
        return remember(42)[1]

    # Act
    result = program()

    # Assert
    assert not isinstance(result, State)
    assert result == 42


def test_aggregate_returns_the_values_of_the_states_in_a_returned_tuple():
    # Arrange
    @aggregate
    def program():
        return remember(1)[1], 2

    # Act
    result = program()

    # Assert
    assert result == (1, 2)
    assert not any(isinstance(item, State) for item in result)

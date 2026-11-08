from dataclasses import dataclass
from typing import NamedTuple

import pytest

from phyelds import engine
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.data import State
from phyelds.vm import Engine
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


def test_aggregate_returns_the_values_of_the_states_nested_in_a_returned_list():
    # Arrange
    @aggregate
    def program():
        return [remember(1)[1], (remember(2)[1], 3)]

    # Act
    result = program()

    # Assert
    assert result == [1, (2, 3)]
    assert not isinstance(result[0], State)
    assert not isinstance(result[1][0], State)


def test_aggregate_returns_the_values_of_the_states_in_a_returned_dict():
    # Arrange
    @aggregate
    def program():
        return {"distance": remember(1.5)[1], remember("key")[1]: [remember(2)[1]]}

    # Act
    result = program()

    # Assert
    assert result == {"distance": 1.5, "key": [2]}
    assert not isinstance(result["distance"], State)
    assert not any(isinstance(key, State) for key in result)
    assert not isinstance(result["key"][0], State)


class Reading(NamedTuple):
    sensor: str
    value: float


def test_aggregate_keeps_the_type_of_a_returned_named_tuple_while_unwrapping_it():
    # Arrange
    @aggregate
    def program():
        return Reading("temperature", remember(21.5)[1])

    # Act
    result = program()

    # Assert
    assert type(result) is Reading
    assert result == Reading("temperature", 21.5)
    assert not isinstance(result.value, State)


def test_aggregate_returns_the_same_object_when_the_result_holds_no_state():
    # Arrange
    readings = {"temperatures": [21.5, (22.0, 23.0)]}

    @aggregate
    def program():
        return readings

    # Act
    result = program()

    # Assert
    assert result is readings
    assert result["temperatures"] is readings["temperatures"]


class _OwnEngine(Engine):
    """An engine written from scratch, whose __init__ does not call Engine's."""

    def __init__(self):  # pylint: disable=super-init-not-called
        self.path, self.states = [], {}

    def enter(self, name):
        self.path.append(name)

    def exit(self):
        self.path.pop()

    def current_path(self):
        return list(self.path)

    def read_state(self, stack):
        return self.states.get(str(stack))

    def write_state(self, value, stack):
        self.states[str(stack)] = value


def test_aggregate_unwraps_states_on_an_engine_that_does_not_call_the_engine_init():
    # Arrange
    engine.set(_OwnEngine())

    @aggregate
    def program():
        return remember(42)[1]

    # Act
    result = program()

    # Assert
    assert result == 42
    assert not isinstance(result, State)


@dataclass(frozen=True)
class Team:
    leader: int
    formed: bool = False


def test_aggregate_keeps_the_type_of_a_returned_dataclass_while_unwrapping_it():
    # Arrange
    @aggregate
    def program():
        return Team(remember(3)[1], formed=True)

    # Act
    result = program()

    # Assert
    assert result == Team(3, formed=True)
    assert not isinstance(result.leader, State)


@pytest.mark.parametrize("kind", [set, frozenset])
def test_aggregate_returns_the_values_of_the_states_in_a_returned_set(kind):
    # Arrange
    @aggregate
    def program():
        return kind({remember(1)[1], 2})

    # Act
    result = program()

    # Assert
    assert type(result) is kind
    assert result == {1, 2}
    assert not any(isinstance(item, State) for item in result)


def test_aggregate_returns_the_values_of_the_states_in_a_returned_field():
    # Arrange
    @aggregate
    def program():
        return neighbors(remember(1)[1])

    # Act
    result = program()

    # Assert
    assert result.local() == 1
    assert not isinstance(result.local(), State)

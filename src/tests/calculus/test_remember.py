import pytest
from phyelds.vm.internal import MutableEngine

from phyelds import engine
from phyelds.calculus import remember, aggregate, align, remember_and_evolve
from tests.calculus.mock import MockSimulator, MockNodeContext


@pytest.fixture(scope="function", autouse=True)
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))

def test_remember_should_add_a_path_to_the_engine():
    remember(0)
    x = engine.get().engine_state.state_trace
    assert str(["remember@0"]) in x

def test_remember_should_increment_the_counter():
    remember(0)
    remember(0)
    x = engine.get().engine_state.state_trace
    assert str(["remember@1"]) in x

def test_remember_should_support_nesting():
    with(align("first")):
        remember(0)
        with(align("second")):
            remember(0)
    x = engine.get().engine_state.state_trace
    assert str(["first@0", "remember@0"]) in x
    assert str(["first@0", "second@1", "remember@0"]) in x


def test_remember_should_give_the_value_itself():
    # Setup
    initial_value = 42
    # Execute
    result, _ = remember(initial_value)
    # Assert
    assert type(result) is int
    assert result == initial_value

def test_remember_should_update_value():
    # Setup
    initial_value = 42
    new_value = 100
    # Execute
    state, update_state = remember(initial_value)
    updated = update_state(new_value)
    # Assert
    assert state == initial_value
    assert updated == new_value


def test_state_could_be_combined():
    # Setup
    assert remember(1)[0] + remember(2)[0] == 3

def test_remember_should_update_value_with_function():
    # Setup
    initial_value = 42
    increment = 10
    # Execute
    state = remember_and_evolve(initial_value, lambda x: x + increment)
    # Assert
    assert state == initial_value + increment

def test_remember_should_not_update_value_with_function_twice():
    # Setup
    def counter():
        return remember_and_evolve(0, lambda x: x + 1)
    # Execute
    state = counter()
    counter()
    # Assert
    assert state == 1

def test_remember_should_have_state_in_different_call():
    simulator = MockSimulator(1)
    @aggregate
    def counter():
        return remember_and_evolve(0, lambda x: x + 1)
    simulator.cycle(counter)
    simulator.cycle(counter)
    assert simulator.nodes[0].root == 2

def test_remember_should_restart_when_dealing():
    simulator = MockSimulator(1)
    @aggregate
    def counter():
        return remember_and_evolve(0, lambda x: x + 1)

    @aggregate
    def double_state():
        if counter() % 2 == 0:
            return remember_and_evolve(0, lambda x: x + 1)
        else:
            return remember_and_evolve(0, lambda x: x + 1)
    simulator.cycle(double_state)
    assert simulator.nodes[0].root == 1
    simulator.cycle(double_state)
    assert simulator.nodes[0].root == 1
    simulator.cycle(double_state)
    assert simulator.nodes[0].root == 1


def test_remember_stores_plain_values_unaffected_by_later_state_updates():
    count, set_count = remember(1)
    _, set_team = remember([count])
    set_team([count])
    set_count(99)
    assert engine.get().state_trace()[str(["remember@1"])] == [1]

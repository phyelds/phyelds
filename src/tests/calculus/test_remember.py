from fieldpy import engine
from fieldpy.calculus import remember
from fieldpy.data import State


def test_remember_should_give_the_value_itself():
    # Setup
    initial_value = 42
    # Execute
    result = remember(initial_value)
    # Assert
    assert isinstance(result, State)
    assert result.value == initial_value

def test_remember_should_update_value():
    # Setup
    initial_value = 42
    new_value = 100
    # Execute
    state = remember(initial_value)
    state.update(new_value)
    # Assert
    assert state.value == new_value

def test_remember_should_update_value_with_function():
    # Setup
    initial_value = 42
    increment = 10
    # Execute
    state = remember(initial_value)
    state.update_fn(lambda x: x + increment)
    # Assert
    assert state.value == initial_value + increment

def test_remember_should_not_update_value_with_function_twice():
    # Setup
    def counter():
        return remember(0).update_fn(lambda x: x + 1)
    # Execute
    state = counter()
    counter()
    # Assert
    assert state == 1

def test_remember_should_have_state_in_different_call():
    engine.setup(0)
    def counter():
        return remember(0).update_fn(lambda x: x + 1)
    counter()
    engine.cooldown()
    engine.setup(0, state=engine.state_trace())
    assert counter() == 2

def test_state_could_be_combined():
    # Setup
    assert remember(1) + remember(2) == 3
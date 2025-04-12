from fieldpy.calculus import neighbors
from fieldpy.data import State


def test_neighbors_should_give_the_value_itself():
    # Setup
    initial_value = 42
    # Execute
    result = neighbors(initial_value)
    # Assert
    assert result.local() == initial_value
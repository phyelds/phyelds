import pytest

from phyelds import engine
from phyelds.calculus import neighbors, remember, align_right, align_left
from tests.calculus.mock import MockSimulator

how_many = 3
def test_neighbors_should_give_the_value_itself():
    engine.setup(0)
    # Setup
    initial_value = 42
    # Execute
    result = neighbors(initial_value)
    # Assert
    assert result.local() == initial_value

def test_neighbors_should_get_value_from_neighbors():
    engine.setup(0)
    # Setup
    initial_value = 1
    simulator = MockSimulator(how_many)
    simulator.cycle_for(lambda context: neighbors(initial_value), how_many * how_many)
    # Execute
    assert(len(list(simulator.nodes[0].root)) == how_many)
    for value in simulator.nodes[0].root:
        assert value == initial_value

def test_neighbors_should_work_as_share():
    engine.setup(0)
    state = remember(0)
    field = neighbors(state)
    state.update(state + 1)
    assert field.local() == 1

def test_neighbors_of_neighbors_should_not_work():
    engine.setup(0)
    with pytest.raises(TypeError):
        neighbors(neighbors(0))

def test_align_should_break_connection():
    simulator = MockSimulator(how_many)
    def program(context):
        if context.node_id < 2:
            with(align_left()):
                return neighbors(context.node_id)
        else:
            with(align_right()):
                return neighbors(context.node_id)
    # Execute
    simulator.cycle_for(program, how_many * how_many)
    # Assert
    assert simulator.nodes[0].root.data == { 0: 0, 1: 1 }
    assert simulator.nodes[1].root.data == { 0: 0, 1: 1 }
    assert simulator.nodes[2].root.data == { 2: 2 }

def test_neighbors_local_should_return_the_value_itself():
    simulator = MockSimulator(how_many)
    def program(context):
        result = neighbors(context.node_id)
        return result
    simulator.cycle_for(program, how_many * how_many)
    for node in simulator.nodes:
        assert node.root.local() == node.node_id

def test_field_support_math_operations():
    simulator = MockSimulator(how_many)
    def program(context):
        return neighbors(1) + 1
    simulator.cycle_for(program, how_many * how_many)
    for node in simulator.nodes:
        assert node.root.local() == 2

def test_field_support_math_operations_between_field():
    simulator = MockSimulator(how_many)
    def program(context):
        return neighbors(1) + neighbors(context.node_id)
    simulator.cycle_for(program, how_many * how_many)
    expected = {
        0: 1,
        1: 2,
        2: 3,
    }

    for node in simulator.nodes:
        assert node.root.data == expected

def test_field_may_be_used_to_exclude_themselves():
    simulator = MockSimulator(how_many)
    def program(context):
        return neighbors(context.node_id).exclude_self()

    simulator.cycle_for(program, how_many * how_many)
    assert simulator.nodes[0].root == { 1: 1, 2: 2 }
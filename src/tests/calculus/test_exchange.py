import pytest
from phyelds import engine
from phyelds.calculus import aggregate, exchange, neighbors
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext, MockSimulator


@pytest.fixture(scope="function", autouse=True)
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))


def test_exchange_returns_initial_value_as_local_in_first_round():
    set_field, field = exchange(42)
    assert callable(set_field)
    assert isinstance(field, NeighborhoodField)
    assert field.local() == 42


def test_exchange_setter_returns_new_value_without_mutating_received_field():
    set_field, field = exchange(10)
    returned = set_field(99)
    assert returned == 99
    assert field.local() == 10


def test_exchange_persists_self_value_across_rounds():
    simulator = MockSimulator(1)
    seen_locals = []

    @aggregate
    def counter():
        set_field, field = exchange(0)
        seen_locals.append(field.local())
        return set_field(field.local() + 1)

    simulator.cycle(counter)
    simulator.cycle(counter)
    assert seen_locals == [0, 1]
    assert simulator.nodes[0].root == 2


def test_exchange_shares_scalar_values_with_neighbors():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        set_field, field = exchange(0)
        set_field(local_id() + 10)
        return field

    simulator.cycle_for(program, 2)
    expected = {0: 10, 1: 11, 2: 12}
    for node in simulator.nodes:
        assert node.root.data == expected


def test_exchange_sends_anisotropic_neighborhood_field_to_each_neighbor():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        ids = neighbors(local_id())
        set_field, field = exchange(0)
        set_field(ids + local_id() * 100)
        return field

    simulator.cycle_for(program, 3)
    assert simulator.nodes[0].root.data == {0: 0, 1: 100, 2: 200}
    assert simulator.nodes[1].root.data == {0: 1, 1: 101, 2: 201}
    assert simulator.nodes[2].root.data == {0: 2, 1: 102, 2: 202}


def test_exchange_uses_field_default_for_unlisted_neighbor():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        set_field, field = exchange(0)
        set_field(NeighborhoodField({0: 10, 1: 20}, local_id(), default=77))
        return field

    simulator.cycle_for(program, 2)
    assert simulator.nodes[1].root.data[0] == 20
    assert simulator.nodes[2].root.data[0] == 77


def test_exchange_keeps_last_sent_field_when_setter_is_not_called():
    simulator = MockSimulator(3)
    round_index = 0

    @aggregate
    def program():
        set_field, field = exchange(0)
        if round_index == 0:
            set_field(NeighborhoodField({0: 10, 1: 20}, local_id(), default=77))
        return field

    simulator.cycle(program)
    round_index = 1
    simulator.cycle(program)
    simulator.cycle(program)
    assert simulator.nodes[0].root.local() == 10
    assert simulator.nodes[1].root.data[0] == 20
    assert simulator.nodes[2].root.data[0] == 77


def test_exchange_splits_communication_across_aligned_branches():
    simulator = MockSimulator(3)

    @aggregate
    def program():
        if local_id() < 2:
            set_field, field = exchange(0)
            set_field(local_id() + 10)
            return field
        set_field, field = exchange(0)
        set_field(local_id() + 10)
        return field

    simulator.cycle_for(program, 2)
    assert simulator.nodes[0].root.data == {0: 10, 1: 11}
    assert simulator.nodes[1].root.data == {0: 10, 1: 11}
    assert simulator.nodes[2].root.data == {2: 12}


def test_exchange_resets_state_when_branch_is_not_taken():
    simulator = MockSimulator(1)

    @aggregate
    def step_counter():
        set_step, step = exchange(0)
        return set_step(step.local() + 1)

    @aggregate
    def alternating():
        if step_counter() % 2 == 0:
            set_field, field = exchange(0)
            return set_field(field.local() + 1)
        set_field, field = exchange(0)
        return set_field(field.local() + 1)

    simulator.cycle(alternating)
    assert simulator.nodes[0].root == 1
    simulator.cycle(alternating)
    assert simulator.nodes[0].root == 1
    simulator.cycle(alternating)
    assert simulator.nodes[0].root == 1






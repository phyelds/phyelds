import pytest
from phyelds.data import NeighborhoodField

def test_creates_neighborhood_and_returns_local_value():
    data = {1: 10, 2: 20, 3: 30}
    neighborhood = NeighborhoodField(data, 2)
    assert neighborhood.local() == 20

def test_iterates_over_neighborhood_values_in_order():
    data = {3: 30, 1: 10, 2: 20}
    neighborhood = NeighborhoodField(data, 1)
    values = list(neighborhood)
    assert values == [10, 20, 30]

def test_exclude_self_removes_node_id_from_data():
    data = {1: 10, 2: 20, 3: 30}
    neighborhood = NeighborhoodField(data, 2)
    result = neighborhood.exclude_self()
    assert 2 not in result
    assert result == {1: 10, 3: 30}

def test_select_returns_values_present_in_both_neighborhoods():
    neighborhood1 = NeighborhoodField({1: 10, 2: 20, 3: 30}, 1)
    neighborhood2 = NeighborhoodField({1: False, 2: True, 3: True}, 2)
    result = neighborhood1.select(neighborhood2)
    assert result == [20, 30]

def test_select_returns_empty_when_no_overlap():
    neighborhood1 = NeighborhoodField({1: 10}, 1)
    neighborhood2 = NeighborhoodField({2: 20}, 2)
    assert neighborhood1.select(neighborhood2) == []

def test_any_returns_true_when_at_least_one_truthy():
    neighborhood = NeighborhoodField({1: False, 2: True, 3: False}, 1)
    assert neighborhood.any() is True

def test_any_returns_false_when_all_falsy():
    neighborhood = NeighborhoodField({1: False, 2: 0, 3: ""}, 1)
    assert neighborhood.any() is False

def test_all_returns_true_when_all_truthy():
    neighborhood = NeighborhoodField({1: True, 2: 1, 3: "text"}, 1)
    assert neighborhood.all() is True

def test_all_returns_false_when_at_least_one_falsy():
    neighborhood = NeighborhoodField({1: True, 2: False, 3: True}, 1)
    assert neighborhood.all() is False

def map_applies_function_to_all_values():
    data = {1: 2, 2: 3}
    neighborhood = NeighborhoodField(data, 1)
    squared = neighborhood.map(lambda x: x * x)
    assert squared.data == {1: 4, 2: 9}

def binary_operations_with_neighborhood_and_scalar():
    f1 = NeighborhoodField({1: 2, 2: 3}, 1)
    f2 = NeighborhoodField({1: 5, 2: 7}, 2)
    assert (f1 + f2).data == {1: 7, 2: 10}
    assert (f1 - 1).data == {1: 1, 2: 2}
    assert (f1 * 2).data == {1: 4, 2: 6}
    assert (f2 // f1).data == {1: 2, 2: 2}

def invert_applies_bitwise_not():
    neighborhood = NeighborhoodField({1: 1, 2: 0}, 1)
    inverted = ~neighborhood
    assert inverted.data == {1: -2, 2: -1}

def comparison_operators_return_expected_results():
    f1 = NeighborhoodField({1: 2, 2: 3}, 1)
    f2 = NeighborhoodField({1: 3, 2: 2}, 2)
    assert (f1 < f2).data == {1: True, 2: False}
    assert (f1 > f2).data == {1: False, 2: True}
    assert (f1 <= 2).data == {1: True, 2: False}

def str_and_repr_return_expected_strings():
    neighborhood = NeighborhoodField({1: 10, 2: 20}, 1)
    s = str(neighborhood)
    r = repr(neighborhood)
    assert "Neighborhood" in s
    assert "id: 1" in r
    assert "local: 10" in r

def next_raises_stopiteration_when_done():
    neighborhood = NeighborhoodField({1: 10}, 1)
    it = iter(neighborhood)
    next(it)
    with pytest.raises(StopIteration):
        next(it)
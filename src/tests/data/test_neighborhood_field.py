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


def test_neighborhood_field_for_node_returns_neighbor_value_or_default():
    neighborhood = NeighborhoodField({1: 10, 2: 20}, 1)
    assert neighborhood.for_node(2) == 20
    assert neighborhood.for_node(99) == 10
    custom_default = NeighborhoodField({1: 10, 2: 20}, 1, default=999)
    assert custom_default.for_node(99) == 999


def test_neighborhood_field_operations_propagate_default():
    first = NeighborhoodField({1: 10, 2: 20}, 1, default=100)
    second = NeighborhoodField({1: 1, 2: 2}, 1, default=5)
    assert first.map(lambda x: x * 2).for_node(99) == 200
    assert (first + 3).for_node(99) == 103
    assert (first + second).for_node(99) == 105
    assert (~NeighborhoodField({1: 0}, 1, default=1)).for_node(99) == -2


def test_without_self_returns_neighborhood_field_excluding_local_node():
    field = NeighborhoodField({1: 10, 2: 20, 3: 30}, 2, default=99)
    peers = field.without_self()
    assert isinstance(peers, NeighborhoodField)
    assert peers.data == {1: 10, 3: 30}
    assert peers.node_id == 2
    assert peers.for_node(99) == 99


def test_ge_operator_compares_values_and_propagates_default():
    field = NeighborhoodField({1: 2, 2: 3}, 1, default=5)
    result = field >= 3
    assert result.data == {1: False, 2: True}
    assert result.for_node(99) is True


def test_fold_and_reduce_collapse_values_with_and_without_self():
    field = NeighborhoodField({1: 10, 2: 20, 3: 30}, 1)
    assert field.fold(0, lambda acc, x: acc + x) == 60
    assert field.fold(0, lambda acc, x: acc + x, include_self=False) == 50
    assert field.reduce(lambda a, b: a + b) == 60
    assert field.reduce(lambda a, b: a + b, include_self=False) == 50
    isolated = NeighborhoodField({1: 10}, 1)
    assert isolated.reduce(lambda a, b: a + b, include_self=False, default=-1) == -1


def test_min_and_max_support_include_self_default_and_key():
    field = NeighborhoodField({1: 5, 2: 20, 3: 10}, 1)
    assert field.min() == 5
    assert field.min(include_self=False) == 10
    assert field.max() == 20
    assert field.max(include_self=False, key=lambda x: -x) == 10
    isolated = NeighborhoodField({1: 5}, 1)
    assert isolated.min(include_self=False, default=float("inf")) == float("inf")
    assert isolated.max(include_self=False, default=float("-inf")) == float("-inf")


def test_sum_and_product_collapse_numeric_fields():
    field = NeighborhoodField({1: 2, 2: 3, 3: 4}, 1)
    assert field.sum() == 9
    assert field.sum(include_self=False) == 7
    assert field.product() == 24
    assert field.product(include_self=False) == 12


def test_predicates_any_all_none_and_count_matching():
    field = NeighborhoodField({1: 1, 2: 4, 3: 6}, 1)
    assert field.count_matching(lambda x: x % 2 == 0) == 2
    assert field.count_matching(lambda x: x > 0, include_self=False) == 2
    assert field.any(lambda x: x == 1) is True
    assert field.any(lambda x: x == 1, include_self=False) is False
    assert field.all(lambda x: x % 2 == 0) is False
    assert field.all(lambda x: x % 2 == 0, include_self=False) is True
    assert field.none(lambda x: x < 0) is True
    assert field.none(lambda x: x == 1, include_self=False) is True
    assert NeighborhoodField({1: False, 2: False}, 1).none() is True


def test_id_of_min_and_id_of_max_return_winning_node_id():
    field = NeighborhoodField({1: 50, 2: 10, 3: 30}, 1)
    assert field.id_of_min() == 2
    assert field.id_of_max() == 1
    assert field.id_of_max(include_self=False) == 3
    assert field.id_of_min(key=lambda node_id, val: -val) == 1
    isolated = NeighborhoodField({1: 50}, 1)
    assert isolated.id_of_min(include_self=False) is None
    assert isolated.id_of_max(include_self=False) is None


def test_coerce_in_and_replace_matching_transform_field():
    field = NeighborhoodField({1: -5, 2: 5, 3: 15}, 1, default=20)
    clamped = field.coerce_in(0, 10)
    assert clamped.data == {1: 0, 2: 5, 3: 10}
    assert clamped.for_node(99) == 10
    with pytest.raises(ValueError):
        field.coerce_in(10, 0)
    replaced = field.replace_matching(0, lambda v: v < 0)
    assert replaced.data == {1: 0, 2: 5, 3: 15}



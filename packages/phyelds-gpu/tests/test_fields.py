"""
The field of a batch of devices: on each device, what a ``NeighborhoodField`` of its own
entries computes.
"""
import math
import operator
import random

import pytest
import torch

from phyelds.data import NeighborhoodField
from phyelds.gpu import BatchField, GraphTopology

NEIGHBORS = {0: [1, 2, 3], 1: [0, 2], 2: [0, 1, 3], 3: [0, 2], 4: []}


def _random_field(seed: int, *, with_local: bool = True) -> BatchField:
    """A field with small integer values, so that ties happen, and some missing entries."""
    rng = random.Random(seed)
    edges = GraphTopology.from_neighbors(NEIGHBORS).batch()
    count = int(edges.senders.numel())
    return BatchField(
        edges,
        torch.tensor([rng.randint(0, 4) for _ in range(5)]),
        torch.tensor([rng.randint(0, 4) for _ in range(count)]),
        torch.tensor([rng.random() < 0.8 for _ in range(count)]),
        local_present=torch.tensor([with_local and rng.random() < 0.8 for _ in range(5)]),
        default=-1,
    )


def _scalar_fields(field: BatchField) -> list[NeighborhoodField]:
    """The ``NeighborhoodField`` of each device of ``field``."""
    entries = {device: {} for device in range(5)}
    for sender, receiver, value, present in zip(
        field.edges.senders.tolist(), field.edges.receivers.tolist(),
        field.values.tolist(), field.present.tolist(),
    ):
        if present:
            entries[receiver][sender] = value
    for device, (value, present) in enumerate(zip(field.local_values.tolist(), field.local_present.tolist())):
        if present:
            entries[device][device] = int(value)
    return [NeighborhoodField(entries[device], device, default=-1) for device in range(5)]


def _plain(value):
    """``value`` as Python numbers, with NaN as ``None``."""
    if isinstance(value, torch.Tensor):
        return [None if isinstance(item, float) and math.isnan(item) else item
                for item in value.tolist()]
    return value


OPERATIONS = {
    "sum": lambda field, own: field.sum(),
    "sum without self": lambda field, own: field.sum(include_self=False, start=2),
    "product": lambda field, own: field.product(),
    "min": lambda field, own: field.min(default=9),
    "max without self": lambda field, own: field.without_self().max(default=-9),
    "id of min": lambda field, own: field.id_of_min(),
    "id of max without self": lambda field, own: field.id_of_max(include_self=False),
    "fold add": lambda field, own: field.fold(10, operator.add),
    "fold mul": lambda field, own: field.fold(2, operator.mul),
    "fold max": lambda field, own: field.fold(-5, max),
    "fold min": lambda field, own: field.fold(7, min),
    "fold or": lambda field, own: (field > 3).fold(False, operator.or_),
    "fold and": lambda field, own: (field > 0).fold(True, operator.and_),
    "any": lambda field, own: field.any(lambda value: value > 3),
    "all": lambda field, own: field.all(lambda value: value > 0),
    "none": lambda field, own: field.none(lambda value: value > 3),
    "any without self": lambda field, own: field.without_self().any(lambda value: value > 1),
    "all without self": lambda field, own: field.without_self().all(lambda value: value > 1),
    "fold or without self": lambda field, own: (field > 1).fold(False, operator.or_, include_self=False),
    "count matching": lambda field, own: field.count_matching(lambda value: value > 1),
    "map with values of the device": lambda field, own: field.map(operator.sub, own).sum(),
    "where": lambda field, own: field.where(field > 1).sum(),
    "field and field": lambda field, own: (field * field - field).max(),
    "field and value of the device": lambda field, own: (field + own).min(),
    "field and number": lambda field, own: (field - 2).max(),
    "with local": lambda field, own: field.with_local(own).sum(),
    "coerce in": lambda field, own: field.coerce_in(1, 3).sum(),
    "inverted": lambda field, own: (~field).sum(),
    "local": lambda field, own: field.with_local(own).local(),
}


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("name", OPERATIONS)
def test_batch_field_computes_on_each_device_what_its_neighborhood_field_does(name, seed):
    field = _random_field(seed)
    own = torch.tensor([3, 1, 4, 1, 5])
    operation = OPERATIONS[name]

    together = _plain(operation(field, own))

    alone = [operation(scalar, own[device].item()) for device, scalar in enumerate(_scalar_fields(field))]
    assert together == alone


def test_batch_field_folds_only_with_reductions_it_can_tell():
    field = _random_field(0)

    with pytest.raises(TypeError, match="operator.add"):
        field.fold(0, lambda total, value: total + value)


def test_batch_field_cannot_be_iterated_as_one():
    with pytest.raises(TypeError, match="reduce"):
        list(_random_field(0))

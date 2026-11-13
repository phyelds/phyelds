"""
Synchronous rounds of every device at once, on a torch device: in each round, what the rounds
of each device on its own compute.
"""
import math
import random

import pytest
import torch

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.libraries.collect import collect_or, count_nodes, sum_values
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.vm.synchronous import SynchronousRuntime
from phyelds.gpu import BatchSynchronousRuntime, radius_topology

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]
COUNT, ROUNDS = 60, 8


@aggregate
def libraries():
    potential = distance_to(sense("source"))
    return (
        potential,
        gossip_max(local_id()),
        count_nodes(potential),
        sum_values(potential, sense("value")),
        collect_or(potential, sense("value") == 3),
    )


@aggregate
def branches():
    value = sense("value")
    if value > 2:
        total = neighbors(value).sum()
    elif value > 1:
        total = 0
    else:
        total = neighbors(1).sum(include_self=False)
    count, set_count = remember(0)
    set_count(count + 1)
    store("total", total)
    return total, count


@aggregate
def early_returns():
    value = sense("value")
    if value > 2:
        return neighbors(value).max()
    shared = neighbors(-value).min()
    if value > 1:
        return shared
    return shared - 1


@aggregate
def expressions():
    value = sense("value")
    small = 0 if value < 2 else 1
    both = value > 1 and neighbors(value).max()
    negated = not value
    return small, both, negated, max(value, 2), min(value, 2, 1)


@aggregate
def state_in_branches():
    value = sense("value")
    if value % 2 == 0:
        count, set_count = remember(0)
        total = set_count(count + value)
    else:
        total, _, send = exchange(value)
        total = send(total + 1)
    return total


PROGRAMS = [libraries, branches, early_returns, expressions, state_in_branches]


def _world(device: str):
    rng = random.Random(11)
    positions = [(rng.uniform(0.0, 6.0), rng.uniform(0.0, 6.0)) for _ in range(COUNT)]
    topology = radius_topology(torch.tensor(positions, dtype=torch.float64, device=device), 1.4)
    values = [device_id % 4 for device_id in range(COUNT)]
    sensors = {
        device_id: {"source": device_id == 0, "value": values[device_id]}
        for device_id in range(COUNT)
    }
    batch_sensors = {
        "source": torch.arange(COUNT, device=device) == 0,
        "value": torch.tensor(values, device=device),
    }
    return topology, sensors, batch_sensors


def _per_device(result, count: int) -> dict:
    """The result of each device, as Python values; NaN, as on a batch engine, is ``None``."""
    def plain(value, index):
        if isinstance(value, tuple):
            return tuple(plain(item, index) for item in value)
        if isinstance(value, torch.Tensor):
            item = value[index].item()
            return None if isinstance(item, float) and math.isnan(item) else item
        return value
    return {index: plain(result, index) for index in range(count)}


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("program", PROGRAMS, ids=lambda program: program.__name__)
def test_batch_runtime_computes_in_each_round_what_each_device_computes_alone(program, device):
    topology, sensors, batch_sensors = _world(device)
    alone = SynchronousRuntime(program)
    together = BatchSynchronousRuntime(program, topology)

    for _ in range(ROUNDS):
        expected = alone.run_round(sensors, topology.to_neighbors())

        actual = _per_device(together.run_round(batch_sensors), COUNT)

        assert actual == expected


def test_batch_runtime_keeps_the_outputs_of_each_device():
    topology, sensors, batch_sensors = _world("cpu")
    alone = SynchronousRuntime(branches)
    together = BatchSynchronousRuntime(branches, topology)

    for _ in range(3):
        alone.run_round(sensors, topology.to_neighbors())
        together.run_round(batch_sensors)

    values, stored = together.outputs["total"]
    assert stored.all()
    assert values.tolist() == [alone.outputs[device_id]["total"] for device_id in range(COUNT)]


def test_batch_runtime_forgets_every_device_on_reset():
    topology, _, batch_sensors = _world("cpu")
    together = BatchSynchronousRuntime(branches, topology)
    first = together.run_round(batch_sensors)
    together.run_round(batch_sensors)

    together.reset()

    assert torch.equal(together.run_round(batch_sensors)[1], first[1])


def _increment(value):
    return value + 1


def _decrement(value):
    return value - 1


@aggregate
def function_chosen_in_branches():
    if sense("value") > 1:
        step = _increment
    else:
        step = _decrement
    return step(0)


def test_batch_runtime_refuses_a_function_that_differs_from_device_to_device():
    topology, _, batch_sensors = _world("cpu")
    together = BatchSynchronousRuntime(function_chosen_in_branches, topology)

    with pytest.raises(TypeError, match="after the if"):
        together.run_round(batch_sensors)

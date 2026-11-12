"""
The rewriting of ``@aggregate`` for vectorized engines: on one device it computes what the
aligned rewriting does, and on many devices at once, what each of them computes on its own,
with the same messages.
"""
import pytest

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.vm.internal import MutableEngine
from phyelds.vm.rounds import run_round
from tests.calculus.lanes import lanes_rounds

ROUNDS = 5
LINE = {0: [1], 1: [0, 2], 2: [1, 3], 3: [2, 4], 4: [3]}
SENSORS = {device: {"value": device % 4, "source": device == 0} for device in LINE}


class VectorizedMutableEngine(MutableEngine):
    """One device at a time, running the code rewritten for vectorized engines."""

    vectorized = True


@aggregate
def branches_assigning_locals():
    value = sense("value")
    if value > 2:
        label = "big"
        total = neighbors(value).sum()
    elif value > 1:
        label = "medium"
        total = 0
    else:
        label = "small"
        total = neighbors(1).sum()
    count, set_count = remember(0)
    set_count(count + 1)
    return label, total, count


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
def nested_branches_without_else():
    value = sense("value")
    result = 0
    if value > 0:
        if value > 2:
            result = neighbors(1).sum()
        result = result + 1
    store("result", result)


@aggregate
def _touched(label):
    store(label, True)
    return neighbors(1).sum()


@aggregate
def expressions():
    value = sense("value")
    small = 0 if value < 2 else 1
    both = value > 1 and _touched("and")
    either = value > 2 or _touched("or")
    negated = not value
    return small, both, either, negated, max(value, 2), min(value, 2, 1)


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


@aggregate
def libraries():
    return distance_to(sense("source")), gossip_max(local_id())


PROGRAMS = [
    branches_assigning_locals,
    early_returns,
    nested_branches_without_else,
    expressions,
    state_in_branches,
    libraries,
]


def _device_rounds(program, engine_type) -> list[dict]:
    """Synchronous rounds of each device on its own: result, outbox, state and outputs."""
    states, outboxes, history = {}, {}, []
    for _ in range(ROUNDS):
        done = {
            device: run_round(
                program, device, SENSORS[device],
                {other: outboxes[other] for other in others if other in outboxes},
                states.get(device), engine_instance=engine_type(),
            )
            for device, others in LINE.items()
        }
        history.append({
            device: (finished.result, finished.outbox, finished.state, finished.outputs)
            for device, finished in done.items()
        })
        outboxes = {device: finished.outbox for device, finished in done.items()}
        states = {device: finished.state for device, finished in done.items()}
    return history


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda program: program.__name__)
def test_vectorized_rewriting_computes_on_one_device_what_the_aligned_one_does(program):
    aligned = _device_rounds(program, MutableEngine)

    vectorized = _device_rounds(program, VectorizedMutableEngine)

    assert vectorized == aligned


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda program: program.__name__)
def test_vectorized_rewriting_computes_on_many_devices_what_each_does_alone(program):
    alone = _device_rounds(program, MutableEngine)

    together = lanes_rounds(program, SENSORS, LINE, ROUNDS)

    assert together == alone


@aggregate
def branch_in_a_loop():
    total = 0
    for step in range(2):
        if sense("value") > step:
            total = total + 1
    return total


def test_vectorized_rewriting_leaves_the_branches_in_loops_to_single_truth_values():
    with pytest.raises(TypeError, match="truth value"):
        lanes_rounds(branch_in_a_loop, SENSORS, LINE, 1)

"""
Programs run on CPython and on MicroPython by test_runtime.py, on a line of devices.

    python programs.py <program> [paths]

prints the encoded results and outboxes of the last round.
"""
import sys

from phyelds import engine
from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import State
from phyelds.data.codec import encode
from phyelds.libraries.collect import collect_with, point_to_point, sum_values
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.gossip import gossip, gossip_max, path_coherent_gossip
from phyelds.libraries.leader_election import candidacy, elect_leader
from phyelds.libraries.logic import boundary, everywhere, previously, somewhere
from phyelds.libraries.processes import bubble, process
from phyelds.libraries.spreading import broadcast, cast_from, distance_to
from phyelds.libraries.time import counter, delay, has_changed, periodic_impulse, time_replicated
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine

# Ids that MicroPython dicts do not keep in order.
IDS = (64, 1000, 17, 5)
ROUNDS = 8


@aggregate
def neighbour_ids():
    return neighbors(local_id()).sum()


@aggregate
def remembered():
    set_count, count = remember(0)
    return set_count(count + 1)


@aggregate
def exchanged():
    set_field, field = exchange(local_id())
    set_field(field.max())
    return field.max()


@aggregate
def branches():
    if sense("source"):
        return neighbors(1).sum()
    return neighbors(10).sum()


@aggregate
def conditional_expression():
    return neighbors(1).sum() if sense("source") else neighbors(10).sum()


@aggregate
def state_arithmetic():
    _, count = remember(3)
    return [count + 1, 1 + count, count * 2, 10 - count, count < 5, count > 2, -count, abs(count),
            count == 3, float(count), int(count), str(count)]


@aggregate
def value_compared_to_state():
    _, count = remember(3)
    return 2 < count


@aggregate
def field_operations():
    field = neighbors(local_id())
    return [(field + 1).sum(), (field * 2).data, field.min(),
            field.max(include_self=False), field.id_of_min(), field.id_of_max(),
            (field > 1).data, field.exclude_self(), field.reduce(lambda a, b: a + b),
            field.fold(0, lambda total, value: total + value), field.count_matching(lambda v: v > 1),
            field.select(field > 1), list(field), field.map(lambda v: v * v).data,
            (field + neighbors(1)).data, field.coerce_in(1, 2).data, field.local(),
            neighbors(str(local_id())).fold("", lambda text, value: text + value + ","),
            neighbors(0).id_of_min(), list(field.exclude_self())]


@aggregate
def gradient():
    return distance_to(sense("source"), hops_distance())


@aggregate
def broadcasted():
    return broadcast(sense("source"), local_id() * 10)


def _hop(from_source, edge, data):
    return data + edge + from_source


@aggregate
def cast_with_a_three_argument_function():
    return cast_from(sense("source"), 0.0, _hop)


@aggregate
def cast_with_a_two_argument_lambda():
    return cast_from(sense("source"), 0.0, lambda edge, data: data + edge)


@aggregate
def collected():
    potential = distance_to(sense("source"), hops_distance())
    return [collect_with(potential, 1, lambda a, b: a + b),
            sum_values(potential, local_id(), strategy=point_to_point())]


@aggregate
def gossiped():
    return [gossip(local_id(), min), gossip_max(local_id()),
            gossip(local_id(), max, strategy=path_coherent_gossip())]


@aggregate
def leader():
    return elect_leader(2, strategy=candidacy(local_id()))


@aggregate
def timed():
    return [counter(), delay(local_id()), has_changed(sense("time")), periodic_impulse(3),
            time_replicated(lambda: gossip(local_id(), min), 3)]


@aggregate
def spatial_logic():
    source = sense("source")
    return [boundary(source), somewhere(source), everywhere(local_id() >= 0), previously(source)]


@process
def area(origin, radius=1.0):
    distance = float(distance_to(local_id() == origin))
    with bubble(inside=distance <= radius):
        return distance


@aggregate
def processes():
    return area.spawn({local_id()} if sense("source") else set(), radius=2.0)


@aggregate
def state_type():
    _, count = remember(3)
    return isinstance(count, int)


def run(program, paths="debug"):
    """Run ``program`` on a line of devices; return the last results and outboxes."""
    states = {device: {} for device in IDS}
    outboxes = {device: {} for device in IDS}
    results = {}
    for time in range(ROUNDS):
        for index, device in enumerate(IDS):
            inbox = {IDS[other]: outboxes[IDS[other]] for other in (index - 1, index + 1) if 0 <= other < len(IDS)}
            sensors = {"source": index == 0, "time": float(time), "position": (index, 0)}
            engine.set(MutableEngine(paths=paths).setup(NodeContext(device, sensors), inbox, states[device]))
            result = program()
            outboxes[device] = engine.get().cooldown()
            states[device] = engine.get().state_trace()
            results[device] = result.value if isinstance(result, State) else result
    return results, outboxes


if __name__ == "__main__":
    print(encode(run(globals()[sys.argv[1]], *sys.argv[2:])).decode())

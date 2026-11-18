from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.device import sense
from phyelds.libraries.distances import hops_distance, neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.ros2 import AggregateNode, WithinRange


@aggregate
def hops_to_source():
    return distance_to(sense("source"), hops_distance())


def _line(names, program, **options):
    return [
        AggregateNode(name, program, sensors=lambda name=name: {"source": name == names[0]}, **options)
        for name in names
    ]


def _everyone_hears_everyone(nodes):
    return {node.device_id: [other.device_id for other in nodes] for node in nodes}


def _run(nodes, links, rounds):
    for time in range(rounds):
        sent = {node.device_id: node.run_round(float(time)) for node in nodes}
        for node in nodes:
            for sender in links.get(node.device_id, ()):
                node.hear(sent[sender])


def test_node_computes_a_gradient_over_the_messages_it_hears():
    nodes = _line(["a", "b", "c"], hops_to_source)

    _run(nodes, {"a": ["b"], "b": ["a", "c"], "c": ["b"]}, rounds=5)

    assert [node.result for node in nodes] == [0, 1, 2]


@aggregate
def neighbour_count():
    return neighbors(1).sum(include_self=False)


def test_node_ignores_its_own_message_on_the_shared_topic():
    nodes = _line(["a", "b"], neighbour_count)

    _run(nodes, {"a": ["a", "b"], "b": ["a", "b"]}, rounds=3)

    assert [node.result for node in nodes] == [1, 1]


@aggregate
def metres_to_source():
    return distance_to(sense("source"), neighbors_distances())


def test_node_measures_its_neighbours_within_range_from_their_positions():
    nodes = _line(["a", "b", "c"], metres_to_source, neighbourhood=WithinRange(1.6))
    for node, x in zip(nodes, [0.0, 1.0, 2.5]):
        node.sense({"position": (x, 0.0, 0.0)})

    _run(nodes, _everyone_hears_everyone(nodes), rounds=5)

    assert [node.result for node in nodes] == [0.0, 1.0, 2.5]


@aggregate
def what_it_senses():
    return sense("position"), sense("battery")


def test_node_senses_the_latest_readings_of_its_topics():
    node = AggregateNode("a", what_it_senses)
    node.sense({"position": (1.0, 0.0, 0.0), "battery": 0.9})
    node.sense({"battery": 0.8})

    node.run_round(0.0)

    assert node.result == ((1.0, 0.0, 0.0), 0.8)


def test_node_measures_no_neighbour_before_its_position_is_sensed():
    node = AggregateNode("a", metres_to_source, neighbourhood=WithinRange(1.0), sensors=lambda: {"source": False})

    node.run_round(0.0)

    assert node.result == float("inf")

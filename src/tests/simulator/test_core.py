import pytest
from src.phyelds.simulator import Node, Environment, Simulator


def test_initializes_with_correct_attributes():
    position = (1.0, 2.0)
    data = {"key": "value"}
    node = Node(position, data)

    assert node.position == position
    assert node.data == data
    assert node.environment is None


def test_updates_position_and_data():
    node = Node((0.0, 0.0))
    new_position = (1.0, 1.0)
    new_data = {"updated": True}

    node.update(new_position=new_position, new_data=new_data)

    assert node.position == new_position
    assert node.data == new_data


def test_returns_empty_neighbors_when_no_environment():
    node = Node((0.0, 0.0))
    assert node.get_neighbors() == []


def test_handles_duplicate_node_ids():
    env = Environment()
    node1 = Node((0.0, 0.0), node_id="duplicate_id")
    node2 = Node((1.0, 1.0), node_id="duplicate_id")

    env.add_node(node1)
    env.add_node(node2)

    assert len(env.node_list()) == 1


def test_adds_and_removes_nodes_correctly():
    env = Environment()
    node = Node((0.0, 0.0))

    env.add_node(node)
    assert node.id in env.nodes

    env.remove_node(node.id)
    assert node.id not in env.nodes


def test_returns_correct_neighbors():
    def mock_neighborhood_function(node, nodes):
        return [n for n in nodes if n.id != node.id]

    env = Environment(neighborhood_function=mock_neighborhood_function)
    node1 = Node((0.0, 0.0))
    node2 = Node((1.0, 1.0))

    env.add_node(node1)
    env.add_node(node2)

    neighbors = env.get_neighbors(node1)
    assert node2 in neighbors
    assert node1 not in neighbors


def test_schedules_and_executes_events():
    sim = Simulator()
    result = []

    def action():
        result.append("executed")

    sim.schedule_event(1.0, action)
    sim.run()

    assert result == ["executed"]


def test_stops_simulation_correctly():
    sim = Simulator()
    result = []

    def action():
        result.append("executed")
        sim.stop()

    sim.schedule_event(1.0, action)
    sim.run()

    assert result == ["executed"]


def test_resets_simulation_state():
    sim = Simulator()
    sim.schedule_event(1.0, lambda: None)
    sim.reset()

    assert sim.event_queue == []
    assert sim.current_time == 0.0
    assert not sim.running

def test_check_reschedules_event():
    sim = Simulator()
    result = []

    def action():
        result.append("executed")
        sim.schedule_event(1.0, action)
    sim.schedule_event(1.0, action)
    sim.run(3.0)

    assert result == ["executed", "executed", "executed"]

def test_node_connects_to_environment():
    env = Environment()
    node = Node((0.0, 0.0))
    env.add_node(node)

    assert node.environment is env


def test_handles_events_with_same_time():
    sim = Simulator()
    results = []

    def action1():
        results.append("action1")

    def action2():
        results.append("action2")

    sim.schedule_event(1.0, action1)
    sim.schedule_event(1.0, action2)
    sim.run()

    assert len(results) == 2
    assert set(results) == {"action1", "action2"}


def test_passes_parameters_to_events():
    sim = Simulator()
    result = []

    def action(value):
        result.append(value)

    sim.schedule_event(1.0, lambda: action("test_value"))
    sim.run()

    assert result == ["test_value"]


def test_cancels_scheduled_event():
    sim = Simulator()
    result = []

    def action():
        result.append("should not execute")

    event_id = sim.schedule_event(1.0, action)
    sim.cancel_event(event_id)
    sim.run()

    assert result == []

def test_cancels_raise_error_if_event_not_found():
    sim = Simulator()
    result = []

    def action():
        result.append("should not execute")

    event_id = sim.schedule_event(1.0, action)
    sim.cancel_event(event_id)
    with pytest.raises(ValueError):
        sim.cancel_event(event_id)
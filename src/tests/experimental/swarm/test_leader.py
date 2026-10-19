import math

import pytest

from phyelds.calculus import aggregate
from phyelds.experimental.swarm import (
    Vector, align_with_leader, is_team_formed, sink_at, spin_around, team_formation,
)
from phyelds.libraries.device import local_id, store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator


def _results(simulator, program, rounds=10):
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(rounds)
    return {node.id: node.data["result"] for node in simulator.environment.nodes.values()}


def _approx(vector):
    return pytest.approx(tuple(vector), abs=1e-9)


def test_sink_at_heads_to_the_leader_along_the_network():
    simulator = setup_up_simulator(3, 3)

    results = _results(simulator, lambda: sink_at(local_id() == 0))

    assert results[0] == Vector()
    assert tuple(results[8]) == _approx(Vector(-1, -1).normalize())


def test_spin_around_turns_clockwise_around_the_leader():
    simulator = setup_up_simulator(2)

    results = _results(simulator, lambda: spin_around(local_id() == 0))

    # the leader is on the left: clockwise is up
    assert tuple(results[1]) == _approx(Vector(0, 1))


def test_align_with_leader_spreads_the_velocity_of_the_leader():
    simulator = setup_up_simulator(5)

    results = _results(simulator, lambda: align_with_leader(local_id() == 0, Vector(local_id(), 1)))

    assert set(results.values()) == {Vector(0, 1)}


def _two_clusters(spacing=1.0):
    simulator = Simulator()
    for node_id in range(10):
        cluster, index = divmod(node_id, 5)
        simulator.create_node((cluster * 20.0 + index * spacing, 0.0), node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(3.5))
    return simulator


@pytest.mark.parametrize("spacing, formed", [(1.0, True), (3.0, False)])
def test_is_team_formed_checks_how_close_every_member_is(spacing, formed):
    results = _results(_two_clusters(spacing), lambda: is_team_formed(local_id() in (0, 5), 1.5))

    assert set(results.values()) == {formed}


def test_team_formation_splits_the_swarm_in_teams_that_gather_around_their_leaders():
    simulator = _two_clusters(spacing=3.0)

    @aggregate
    def program():
        team = team_formation(1.0, 30.0, condition=lambda leader: is_team_formed(leader, 2.5))
        store("velocity", team.velocity)
        return team

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=0.2)
    simulator.run(100)
    teams = {node.id: node.data["result"] for node in simulator.environment.nodes.values()}

    # gathering may split a cluster before its election settles: each part is a team
    assert all(team.formed and team.velocity == Vector() for team in teams.values())
    assert all(teams[team.leader].leader == team.leader for team in teams.values())
    assert all(node_id // 5 == team.leader // 5 for node_id, team in teams.items())


def test_team_inside_runs_a_behaviour_per_team():
    simulator = _two_clusters()

    @aggregate
    def program():
        team = team_formation(1.0, 5.0, leader=local_id() in (0, 5), condition=lambda leader: True)
        return team.inside(lambda leader: align_with_leader(local_id() == leader, Vector(leader, 0)))

    results = _results(simulator, program, rounds=20)

    assert [results[node_id] for node_id in (1, 4, 6, 9)] == [Vector(), Vector(), Vector(5, 0), Vector(5, 0)]
    assert math.isclose(results[0].x, 0.0)


def test_team_formation_forms_as_soon_as_the_leader_is_known_without_a_condition():
    simulator = _two_clusters()

    @aggregate
    def program():
        return team_formation(1.0, 30.0, leader=local_id() in (0, 5))

    teams = _results(simulator, program)

    assert all(team.formed for team in teams.values())
    assert {team.leader for team in teams.values()} == {0, 5}

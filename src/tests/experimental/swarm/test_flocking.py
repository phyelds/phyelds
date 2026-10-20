import random

import pytest

from phyelds.calculus import remember_and_evolve
from phyelds.experimental.swarm import (
    Vector, alignment, brownian, cohesion, cucker_smale, reynolds, separation, vicsek,
)
from phyelds.libraries.device import local_id, sense, store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import full_neighborhood, radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all


def _line(*xs, radius=None):
    simulator = Simulator()
    for node_id, x in enumerate(xs):
        simulator.create_node((x, 0.0), node_id=node_id)
    simulator.environment.set_neighborhood_function(
        full_neighborhood if radius is None else radius_neighborhood(radius)
    )
    return simulator


def _results(simulator, program, rounds=2):
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(rounds)
    return [node.data["result"] for node in simulator.environment.nodes.values()]


def test_separation_heads_away_from_the_neighbors():
    left, middle, right = _results(_line(0, 1, 3), lambda: separation(Vector()))

    assert left == Vector(-1, 0)
    assert right == Vector(1, 0)
    assert middle == Vector(-1, 0)


def test_separation_ignores_the_neighbors_out_of_range():
    left, _, _ = _results(_line(0, -1, 3), lambda: separation(Vector(), within=2.0))

    assert left == Vector(1, 0)


def test_separation_counts_only_the_nearest_neighbors():
    left, _, _ = _results(_line(0, -1, 3), lambda: separation(Vector(), nearest=1))

    assert left == Vector(1, 0)


def test_separation_subtracts_the_previous_velocity():
    left, _ = _results(_line(0, 1), lambda: separation(Vector(0, 1)))

    assert left == Vector(-1, -1)


def test_cohesion_heads_to_the_neighbors():
    left, _, right = _results(_line(0, 1, 3), lambda: cohesion(Vector()))

    assert (left, right) == (Vector(1, 0), Vector(-1, 0))


def test_alignment_heads_like_the_neighbors():
    headings = [Vector(1, 0), Vector(0, 1), Vector(0, 1)]

    first, _, _ = _results(_line(0, 1, 2), lambda: alignment(headings[local_id()]))

    assert first == Vector(0, 1) - Vector(1, 0)


def test_blocks_are_zero_without_neighbors():
    alone, = _results(_line(0), lambda: (separation(Vector(1, 0)), alignment(Vector(1, 0)), cohesion(Vector(1, 0))))

    assert alone == (Vector(), Vector(), Vector())


def test_reynolds_sums_the_weighted_directions_with_the_previous_velocity():
    left, _ = _results(_line(0, 1), lambda: reynolds(Vector(), separation_weight=2.0, cohesion_weight=1.0))

    # separation pushes left twice as much as cohesion pulls right; no velocity to align with
    assert left == Vector(-1, 0)


def _order(simulator) -> float:
    headings = [node.data["outputs"]["velocity"].normalize() for node in simulator.environment.nodes.values()]
    return sum(headings, Vector()).length() / len(headings)


# Reynolds also separates and gathers the swarm, and steers by unit headings: it aligns
# the swarm less than the models that only average velocities.
@pytest.mark.parametrize("rule, order", [
    (lambda velocity: vicsek(velocity, alpha=0.5, noise=0.01), 0.95),
    (lambda velocity: cucker_smale(velocity, strength=0.02, noise=0.01), 0.95),
    (lambda velocity: reynolds(velocity, separation_within=0.5, cohesion_weight=0.2).limit(1.0), 0.8),
])
def test_flocking_rules_align_a_swarm(rule, order):
    random.seed(7)
    simulator = Simulator()
    for node_id in range(12):
        simulator.create_node((random.uniform(0, 3), random.uniform(0, 3)), node_id=node_id)
        simulator.environment.nodes[node_id].data["heading"] = brownian()
    simulator.environment.set_neighborhood_function(radius_neighborhood(5.0))

    def program():
        velocity = remember_and_evolve(sense("heading"), lambda previous: rule(previous.value)).value
        store("velocity", velocity.limit(1.0))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=0.1)
    simulator.run(1)
    initial = _order(simulator)
    simulator.run(60)

    assert initial < 0.6
    assert _order(simulator) > order

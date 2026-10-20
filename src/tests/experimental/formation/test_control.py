import itertools
import random

import pytest

from phyelds.experimental.formation import circle, formation, lattice_velocity, voronoi_centroid
from phyelds.experimental.swarm import Vector
from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device


def test_voronoi_centroid_is_the_device_alone_in_a_large_shape():
    centroid = voronoi_centroid(circle((0, 0), 10), Vector(), [], reach=1.0)

    assert tuple(centroid) == pytest.approx((0, 0, 0), abs=1e-9)


def test_voronoi_centroid_moves_away_from_a_neighbor():
    centroid = voronoi_centroid(circle((0, 0), 10), Vector(), [Vector(1, 0)], reach=1.0)

    assert centroid.x < -0.1 and centroid.y == pytest.approx(0, abs=1e-9)


def test_voronoi_centroid_moves_away_from_the_border_inside_the_shape():
    centroid = voronoi_centroid(circle((0, 0), 2), Vector(1.8, 0), [], reach=1.0)

    assert centroid.x < -0.1


def test_voronoi_centroid_moves_away_from_a_neighbor_in_space():
    centroid = voronoi_centroid(circle((0, 0, 0), 10), Vector(), [Vector(0, 0, 1)], reach=1.0, dimensions=3)

    assert centroid.z < -0.1


def test_lattice_velocity_pulls_a_device_outside_into_the_shape():
    def program():
        return lattice_velocity(circle((0, 0), 1), Vector(5, 0), [], reach=1.0)

    device = Device(0, program)
    device.run_round({})

    assert tuple(device.result) == pytest.approx((-1, 0, 0), abs=1e-6)


def test_lattice_velocity_slows_down_after_an_overshoot():
    positions = iter([Vector(5, 0), Vector(-5, 0)])

    def program():
        return lattice_velocity(circle((20, 0), 1) | circle((-20, 0), 1), next(positions), [], reach=1.0)

    device = Device(0, program)
    device.run_round({})
    device.run_round({})

    assert device.result.length() == pytest.approx(0.5)


def _jain(positions, shape, low, high, step):
    """Jain's index of the shares of the shape owned by each robot, as the experiments measure it."""
    axes = [[low + (index + 0.5) * step for index in range(int((high - low) / step))]] * len(positions[0])
    shares = [0] * len(positions)
    for sample in itertools.product(*axes):
        if shape.inside(sample):
            nearest = min(
                range(len(positions)), key=lambda index: (Vector(*positions[index]) - Vector(*sample)).length()
            )
            shares[nearest] += 1
    return sum(shares) ** 2 / (len(shares) * sum(share * share for share in shares))


def _spread(shape, starts, *, reach, dimensions, rounds):
    simulator = Simulator()
    for node_id, start in enumerate(starts):
        simulator.create_node(start, node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(2 * reach))

    def program():
        store("velocity", formation(shape, reach=reach, dimensions=dimensions))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=0.3)
    simulator.run(rounds)
    return [node.position for node in simulator.environment.nodes.values()]


def test_formation_spreads_a_swarm_evenly_over_a_shape():
    random.seed(2)
    shape = circle((0, 0), 3)
    starts = [(random.uniform(-7, -5), random.uniform(-1, 1)) for _ in range(12)]

    positions = _spread(shape, starts, reach=1.5, dimensions=2, rounds=60)

    assert all(shape.inside(position) for position in positions)
    assert _jain(positions, shape, -3, 3, 0.25) > 0.95


def test_formation_spreads_a_swarm_in_space():
    random.seed(2)
    shape = circle((0, 0, 0), 2)
    starts = [(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-0.2, 0.2)) for _ in range(8)]

    positions = _spread(shape, starts, reach=1.5, dimensions=3, rounds=60)

    assert all(shape.inside(position) for position in positions)
    assert _jain(positions, shape, -2, 2, 0.4) > 0.95


def test_voronoi_centroid_is_the_device_in_a_cell_too_small_to_sample_in_space():
    crowd = [Vector(x, y, z) * 0.05 for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]

    centroid = voronoi_centroid(circle((0, 0, 0), 10), Vector(), crowd, reach=1.0, dimensions=3)

    assert centroid == Vector()


def test_formation_takes_another_control():
    device = Device(0, lambda: formation(
        circle((0, 0), 1), reach=1.0, control=lambda shape, position, offsets: Vector(shape(position), 0)
    ))
    device.run_round({"position": (3, 0)})

    assert device.result == Vector(2, 0)

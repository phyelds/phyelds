import random

import pytest

from phyelds.experimental.formation import (
    Frame, aligned, anchor_positioning, circle, lattice_velocity, place_shape, self_aligned,
)
from phyelds.experimental.swarm import Vector
from phyelds.libraries.device import sense, store
from phyelds.simulator import Simulator
from phyelds.simulator.actions import follow_velocity
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device
from tests.experimental.formation.test_control import _jain


def test_aligned_moves_by_the_velocity_but_keeps_the_references_still():
    assert aligned(Frame(Vector()), Vector(1, 0)) == Vector(1, 0)
    assert aligned(Frame(Vector(), is_leader=True), Vector(1, 0)) == Vector()
    assert aligned(Frame(None), None) == Vector()


@pytest.mark.parametrize("estimate", [
    lambda world: Vector(world.x, -world.y),  # a mirror image of the world
    lambda world: Vector(-world.y, world.x),  # the world turned by a quarter turn
])
def test_self_aligned_learns_how_its_frame_is_turned(estimate):
    random.seed(3)
    world = Vector()
    device = Device(0, lambda: self_aligned(Frame(sense("estimate")), Vector(0, 1)))
    for _ in range(60):
        device.run_round({"estimate": estimate(world)})
        world = world + device.result

    # once confident, it heads where the frame says, whatever the body frame
    before = estimate(world)
    device.run_round({"estimate": before})
    after = estimate(world + device.result)
    assert tuple((after - before).normalize()) == pytest.approx((0, 1, 0), abs=1e-6)


def test_self_aligned_waits_for_a_frame_then_probes():
    device = Device(0, lambda: self_aligned(Frame(None), None, max_frame_wait=3))
    commands = []
    for _ in range(5):
        device.run_round({})
        commands.append(device.result)

    assert commands[:3] == [Vector()] * 3
    assert [command.length() for command in commands[3:]] == pytest.approx([1.0, 1.0])


def test_anchors_and_self_alignment_spread_a_swarm_that_senses_only_distances():
    random.seed(1)
    simulator = Simulator()
    for node_id in range(16):
        simulator.create_node((random.uniform(0, 3), random.uniform(0, 3)), node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(4.0))
    shape = circle((0, 0), 4)

    def program():
        frame = anchor_positioning(side=1.5, min_height=0.8)
        placed = place_shape(frame, shape)
        velocity = None
        if frame.position is not None:
            velocity = lattice_velocity(placed, frame.position, frame.offsets, reach=2.0)
        store("velocity", self_aligned(frame, velocity, min_energy=2.0))
        return frame.position, placed

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    for node in simulator.environment.nodes.values():
        simulator.schedule_event(0.5, follow_velocity, simulator, 1.0, node, max_speed=0.3)
    simulator.run(100)
    results = [node.data["result"] for node in simulator.environment.nodes.values()]
    placed = results[0][1]
    center = placed.deepest_point_from((0, 0))
    positions = [position for position, _ in results]

    assert all(position is not None and placed.inside(position) for position in positions)
    assert _jain([(position - center).position(2) for position in positions], shape, -4, 4, 0.25) > 0.95

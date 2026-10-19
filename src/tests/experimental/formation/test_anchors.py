import itertools
import math
import random

import pytest

from phyelds.experimental.formation import anchor_positioning
from phyelds.simulator import Simulator
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device


def _anchored(simulator, rounds=30):
    schedule_program_for_all(simulator, 0.0, 1.0, anchor_positioning)
    simulator.run(rounds)
    return {node.id: node.data["result"] for node in simulator.environment.nodes.values()}


def test_anchor_positioning_locates_the_robots_up_to_a_rigid_motion():
    random.seed(5)
    simulator = Simulator()
    true = {node_id: (random.uniform(0, 10), random.uniform(0, 10)) for node_id in range(15)}
    for node_id, position in true.items():
        simulator.create_node(position, node_id=node_id)
    # every robot hears every other: path distances are straight distances
    simulator.environment.set_neighborhood_function(radius_neighborhood(100.0))

    frames = _anchored(simulator)

    for first, second in itertools.combinations(true, 2):
        estimated = (frames[first].position - frames[second].position).length()
        assert estimated == pytest.approx(math.dist(true[first], true[second]), abs=1e-6)


def test_anchor_positioning_elects_three_anchors_that_fix_the_frame():
    simulator = Simulator()
    for node_id in range(16):
        row, column = divmod(node_id, 4)
        simulator.create_node((column * 2.0, row * 2.0), node_id=node_id)
    simulator.environment.set_neighborhood_function(radius_neighborhood(100.0))

    frames = _anchored(simulator)
    anchors = [node_id for node_id, frame in frames.items() if frame.is_reference]

    assert len(anchors) == 3 and frames[0].is_leader and 0 in anchors
    assert tuple(frames[0].position) == pytest.approx((0, 0, 0), abs=1e-9)
    second = next(node_id for node_id in anchors if node_id != 0 and frames[node_id].position.y == pytest.approx(0))
    assert frames[second].position.x > 0
    third, = (node_id for node_id in anchors if node_id not in (0, second))
    assert frames[third].position.y > 0


def test_anchor_positioning_does_not_know_where_a_robot_alone_is():
    device = Device(1, anchor_positioning)
    device.run_round({"position": (7, 7)})

    assert device.result.position is None

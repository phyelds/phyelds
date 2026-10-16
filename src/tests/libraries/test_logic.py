import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.logic import (
    boundary,
    closure,
    closure_boundary,
    everywhere,
    historically,
    interior,
    interior_boundary,
    previously,
    reaches,
    since,
    somewhere,
    surrounds,
    touches,
    yesterday,
)
from phyelds.libraries.spreading import path_coherent
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator


def test_slcs_local_topological_operators_on_line():
    # Line: 0 - 1 - 2 - 3 - 4
    # Region holds on {0, 1, 2}:
    # - interior: {0, 1} (node 2 neighbors 3 which is False)
    # - closure: {0, 1, 2, 3} (node 3 neighbors 2 which is True)
    # - interior_boundary: {2}
    # - closure_boundary: {3}
    # - boundary: {2, 3}
    simulator = setup_up_simulator(5)

    @aggregate
    def program():
        in_reg = local_id() <= 2
        return (
            interior(in_reg),
            closure(in_reg),
            boundary(in_reg),
            interior_boundary(in_reg),
            closure_boundary(in_reg),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(3)

    assert simulator.environment.nodes[0].data["result"] == (True, True, False, False, False)
    assert simulator.environment.nodes[1].data["result"] == (True, True, False, False, False)
    assert simulator.environment.nodes[2].data["result"] == (False, True, True, True, False)
    assert simulator.environment.nodes[3].data["result"] == (False, True, True, False, True)
    assert simulator.environment.nodes[4].data["result"] == (False, False, False, False, False)


def test_slcs_somewhere_everywhere_reaches_and_touches():
    # Line: 0 - 1 - 2 - 3 - 4
    # Region A = {0, 1}, Region B = {3, 4}, Target = {2}
    # Component {0, 1} touches {2} (since 1 is adjacent to 2), but does not reach {2}
    # directly inside {0, 1} because 2 is not in {0, 1}.
    simulator = setup_up_simulator(5)

    @aggregate
    def program():
        reg_a = local_id() <= 1
        target = local_id() == 2
        far_target = local_id() == 4
        return (
            somewhere(target, max_diameter=10),
            everywhere(local_id() >= 0, max_diameter=10),
            reaches(local_id() <= 2, target, max_diameter=10),
            touches(reg_a, target, max_diameter=10),
            touches(reg_a, far_target, max_diameter=10),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(8)

    # Nodes 0 and 1 are in reg_a: they reach target=2 within {0,1,2}, touch {2}, do not touch {4}
    assert simulator.environment.nodes[0].data["result"] == (True, True, True, True, False)
    assert simulator.environment.nodes[1].data["result"] == (True, True, True, True, False)
    # Node 3 is not in {0, 1, 2} nor reg_a
    assert simulator.environment.nodes[3].data["result"] == (True, True, False, False, False)


def test_slcs_surrounds_detects_region_enclosed_by_barrier():
    # Line: 0 - 1 - 2 - 3 - 4
    # Region = {0, 1, 2}, Barrier = {2}, Outside = {3, 4}.
    # Nodes {0, 1} cannot reach Outside {3, 4} without crossing Barrier {2},
    # so surrounds(region, barrier) holds at {0, 1}.
    simulator = setup_up_simulator(5)

    @aggregate
    def program():
        region = local_id() <= 2
        barrier = local_id() == 2
        return surrounds(region, barrier, max_diameter=10, strategy=path_coherent(10))

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    assert simulator.environment.nodes[0].data["result"] is True
    assert simulator.environment.nodes[1].data["result"] is True
    assert simulator.environment.nodes[2].data["result"] is False
    assert simulator.environment.nodes[3].data["result"] is False
    assert simulator.environment.nodes[4].data["result"] is False


def test_past_ctl_local_and_spatiotemporal_operators():
    # Line: 0 - 1 - 2
    simulator = setup_up_simulator(3)
    for i in range(3):
        simulator.environment.nodes[i].data["trig"] = i == 0
        simulator.environment.nodes[i].data["sust"] = True

    @aggregate
    def program():
        trig = sense("trig")
        sust = sense("sust")
        return (
            yesterday(trig, scope="local"),
            yesterday(trig, scope="any"),
            previously(trig, scope="local"),
            previously(trig, scope="any"),
            historically(sust, scope="all"),
            since(sust, trig, scope="any"),
        )

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    # Round 1 (t=0)
    simulator.run(0.0)
    # At round 1 on node 0: yesterday(local)=False, previously(local)=True
    assert simulator.environment.nodes[0].data["result"][0] is False
    assert simulator.environment.nodes[0].data["result"][2] is True

    # Turn off trig on node 0, run 3 more rounds: EP(trig) and ES(sust, trig) spread to all nodes
    simulator.environment.nodes[0].data["trig"] = False
    simulator.continue_run(1.0)
    # At t=1.0, node 0 and node 1 saw trig yesterday in "any" scope
    assert simulator.environment.nodes[0].data["result"][0] is True
    assert simulator.environment.nodes[1].data["result"][1] is True

    simulator.continue_run(3.0)
    for i in range(3):
        _, _, prev_local, prev_any, hist_all, since_any = (
            simulator.environment.nodes[i].data["result"]
        )
        assert prev_local is (i == 0)
        assert prev_any is True
        assert hist_all is True
        assert since_any is True

    # Break sustained on all nodes: since_any becomes False, historically(all) becomes False
    for i in range(3):
        simulator.environment.nodes[i].data["sust"] = False
    simulator.continue_run(2.0)
    for i in range(3):
        _, _, _, prev_any, hist_all, since_any = (
            simulator.environment.nodes[i].data["result"]
        )
        assert prev_any is True
        assert hist_all is False
        assert since_any is False

    with pytest.raises(ValueError):
        yesterday(True, scope="invalid")

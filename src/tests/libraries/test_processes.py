import pytest

from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.processes import (
    BUBBLE,
    EXTERNAL,
    OUTPUT,
    TERMINATED,
    ProcessOutput,
    ProcessStatus,
    bubble,
    emit_if,
    in_bubble,
    process,
    spawn,
    terminate_if,
)
from phyelds.libraries.spreading import broadcast, distance_to
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device
from tests.libraries.simulator_utils import setup_up_simulator


def test_spawn_propagates_within_spatial_bubble_and_stops_at_external():
    # Line 0 - 1 - 2 - 3 - 4; node 0 spawns process 0 bounded to distance <= 2
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def limited_gradient(pid: int) -> tuple[float, bool]:
        dist = float(distance_to(local_id() == pid))
        return dist, dist <= 2.0

    @aggregate
    def program():
        new_keys = {local_id()} if sense("source") else set()
        return spawn(limited_gradient, new_keys)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    assert simulator.environment.nodes[0].data["result"] == {0: 0.0}
    assert simulator.environment.nodes[1].data["result"] == {0: 1.0}
    assert simulator.environment.nodes[2].data["result"] == {0: 2.0}
    assert simulator.environment.nodes[3].data["result"] == {}
    assert simulator.environment.nodes[4].data["result"] == {}


def test_spawn_bubble_status_forwards_process_without_emitting_output():
    simulator = setup_up_simulator(4)
    simulator.environment.nodes[0].data["source"] = True

    @aggregate
    def relay_process(pid: int, max_hops: float) -> ProcessOutput[float]:
        dist = float(distance_to(local_id() == pid))
        if dist > max_hops:
            return ProcessOutput(dist, EXTERNAL)
        # Node 1 acts as an internal relay (BUBBLE), nodes 0 and 2 emit OUTPUT
        status = BUBBLE if local_id() == 1 else OUTPUT
        return ProcessOutput(dist, status)

    @aggregate
    def program():
        keys = {local_id()} if sense("source") else set()
        return spawn(relay_process, keys, args=2.0)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    assert simulator.environment.nodes[0].data["result"] == {0: 0.0}
    assert simulator.environment.nodes[1].data["result"] == {}
    assert simulator.environment.nodes[2].data["result"] == {0: 2.0}
    assert simulator.environment.nodes[3].data["result"] == {}


def test_spawn_aligns_overlapping_processes_and_preserves_subsequent_calls():
    # Node 0 spawns pid=0, Node 4 spawns pid=4, both with radius 2.
    # Node 2 is in both bubbles; subsequent neighbors() call must stay aligned.
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[4].data["source"] = True

    @aggregate
    def proc(pid: int, radius: float) -> tuple[float, ProcessStatus]:
        dist = float(distance_to(local_id() == pid))
        return dist, OUTPUT if dist <= radius else EXTERNAL

    @aggregate
    def program():
        keys = {local_id()} if sense("source") else set()
        active = spawn(proc, keys, args=2.0)
        nbr_count = len(neighbors(local_id()).data)
        return active, nbr_count

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    assert simulator.environment.nodes[0].data["result"] == ({0: 0.0}, 2)
    assert simulator.environment.nodes[1].data["result"] == ({0: 1.0}, 3)
    assert simulator.environment.nodes[2].data["result"] == ({0: 2.0, 4: 2.0}, 3)
    assert simulator.environment.nodes[3].data["result"] == ({4: 1.0}, 3)
    assert simulator.environment.nodes[4].data["result"] == ({4: 0.0}, 2)


def test_spawn_terminated_status_extinguishes_entire_bubble_without_reinfection():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["spawn"] = True
    for node in simulator.environment.nodes.values():
        node.data["stop"] = False
        if node.id != 0:
            node.data["spawn"] = False

    @aggregate
    def stoppable_gradient(pid: int) -> ProcessOutput[float]:
        dist = float(distance_to(local_id() == pid))
        if local_id() == pid and sense("stop"):
            return ProcessOutput(dist, TERMINATED)
        return ProcessOutput(dist, OUTPUT if dist <= 4.0 else EXTERNAL)

    @aggregate
    def program():
        keys = {0} if sense("spawn") else set()
        return spawn(stoppable_gradient, keys)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(8)
    # Stop generating new keys on node 0: the bubble stays alive on its own
    simulator.environment.nodes[0].data["spawn"] = False
    simulator.continue_run(4)
    for i in range(5):
        assert simulator.environment.nodes[i].data["result"] == {0: float(i)}

    # Trigger termination at the origin node 0: the whole bubble shuts down cleanly
    simulator.environment.nodes[0].data["stop"] = True
    simulator.continue_run(10)
    for i in range(5):
        assert simulator.environment.nodes[i].data["result"] == {}


def test_process_decorator_with_guard_functions_and_early_exit():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["smoke"] = True
    for i in range(1, 5):
        simulator.environment.nodes[i].data["smoke"] = False
    executed_inside_body: list[int] = []

    @process
    def smoke_alert(origin: int, radius: float = 2.0) -> int:
        is_origin = local_id() == origin
        dist = float(distance_to(is_origin))
        terminate_if(is_origin and not sense("smoke"))
        in_bubble(dist <= radius)
        executed_inside_body.append(local_id())
        emit_if(local_id() != 1)
        total = int(count_nodes(dist))
        return int(broadcast(is_origin, total))

    @aggregate
    def program():
        triggers = {local_id()} if sense("smoke") else set()
        return smoke_alert.spawn(triggers, radius=2.0)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    # Nodes 0, 1, 2 are in the bubble (total=3); node 1 is BUBBLE (silent), 0 and 2 emit 3.
    # Nodes 3 and 4 exited at in_bubble() without running the body after it.
    assert simulator.environment.nodes[0].data["result"] == {0: 3}
    assert simulator.environment.nodes[1].data["result"] == {}
    assert simulator.environment.nodes[2].data["result"] == {0: 3}
    assert simulator.environment.nodes[3].data["result"] == {}
    assert 3 not in executed_inside_body
    assert 4 not in executed_inside_body

    # Clear smoke on origin 0: bubble terminates across all nodes
    simulator.environment.nodes[0].data["smoke"] = False
    simulator.continue_run(8)
    for i in range(5):
        assert simulator.environment.nodes[i].data["result"] == {}


def test_process_with_bubble_context_manager_and_plain_tuple_return():
    simulator = setup_up_simulator(4)
    simulator.environment.nodes[0].data["active"] = True
    for i in range(1, 4):
        simulator.environment.nodes[i].data["active"] = False

    @process
    def tracker(target_id: int, max_hops: float = 2.0) -> tuple[int, int]:
        is_target = local_id() == target_id
        dist = float(distance_to(is_target))
        with bubble(
            inside=dist <= max_hops,
            terminate=is_target and not sense("active"),
            emit=dist <= 1.0,
        ):
            size = int(count_nodes(dist))
            return target_id, int(broadcast(is_target, size))

    @aggregate
    def program():
        keys = {local_id()} if sense("active") else set()
        return tracker.spawn(keys, max_hops=2.0)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)

    assert simulator.environment.nodes[0].data["result"] == {0: (0, 3)}
    assert simulator.environment.nodes[1].data["result"] == {0: (0, 3)}
    assert simulator.environment.nodes[2].data["result"] == {}
    assert simulator.environment.nodes[3].data["result"] == {}



@pytest.mark.parametrize("paths", ["debug", "compact"])
def test_spawn_aligns_the_processes_of_devices_whatever_their_paths(paths):
    @aggregate
    def program():
        return spawn(lambda pid: (neighbors(1).sum(), True), {local_id()})

    devices = [Device(device_id, program, paths=paths) for device_id in (1, 2)]
    for _ in range(3):
        first, second = (device.run_round({}) for device in devices)
        devices[0].receive(2, second)
        devices[1].receive(1, first)

    assert [device.result for device in devices] == [{1: 2, 2: 2}, {1: 2, 2: 2}]

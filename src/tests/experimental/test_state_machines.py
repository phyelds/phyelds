import pytest

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import Next, collective_state_machine
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.time import counter
from phyelds.vm.device import Device
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator


def _states(simulator) -> list:
    return [node.data["result"] for node in simulator.environment.nodes.values()]


# The states of Example 1 of the paper, in their total order.
WAIT, WANDER, SOLVE, DEFEND = range(4)


def _run(simulator, transition, rounds: int = 10, initial: int = WAIT):
    @aggregate
    def program():
        return collective_state_machine(initial, transition)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(rounds)


def test_collective_state_machine_spreads_a_transition_proposed_by_one_device():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    _run(simulator, lambda state: Next(WANDER, priority=0.0) if sense("source") else state)

    assert _states(simulator) == [WANDER] * 5


def test_collective_state_machine_keeps_staying_over_a_smaller_state_of_the_same_priority():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    # Staying is the final self-loop (-inf, SOLVE) of every history, which is greater
    # than the transition (-inf, WAIT) at the same position (Definitions 4 and 5).
    _run(simulator, lambda state: WAIT if sense("source") else state, initial=SOLVE)

    assert _states(simulator) == [SOLVE] * 5


def test_collective_state_machine_settles_a_conflict_with_the_higher_priority():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[4].data["target"] = True

    def transition(state):
        if state == WAIT and sense("source"):
            return Next(DEFEND, priority=1.0)
        if state == WAIT and sense("target"):
            return Next(SOLVE, priority=5.0)
        return state

    _run(simulator, transition)

    assert _states(simulator) == [SOLVE] * 5


def test_collective_state_machine_settles_a_conflict_of_equal_priority_with_the_greater_state():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[4].data["target"] = True

    def transition(state):
        if state == WAIT and sense("source"):
            return Next(SOLVE, priority=1.0)
        if state == WAIT and sense("target"):
            return Next(WANDER, priority=1.0)
        return state

    _run(simulator, transition)

    assert _states(simulator) == [SOLVE] * 5


def test_collective_state_machine_runs_each_state_on_its_own_alignment():
    # Without alignment, the counter of WAIT would go on counting in WANDER.
    def transition(state):
        if counter() < 3:
            return state
        return WANDER if state == WAIT else WAIT

    device = Device(0, lambda: collective_state_machine(WAIT, transition))
    states = []
    for _ in range(9):
        device.run_round({})
        states.append(device.result)

    assert states == [WAIT] * 3 + [WANDER] * 3 + [WAIT] * 3


def test_collective_state_machine_agrees_over_messages_sent_as_bytes():
    def program():
        return collective_state_machine(WAIT, lambda state: Next(WANDER, 0.0) if sense("source") else state)

    devices = [Device(0, program), Device(1, program)]
    for _ in range(3):
        payloads = [device.run_round({"source": device.device_id == 0}) for device in devices]
        devices[0].receive(1, payloads[1])
        devices[1].receive(0, payloads[0])

    assert [device.result for device in devices] == [WANDER, WANDER]


def _payload_sizes(memory, rounds: int = 40) -> list[int]:
    device = Device(0, lambda: collective_state_machine(0, lambda state: state + 1, memory=memory))
    return [len(device.run_round({})) for _ in range(rounds)]


def test_collective_state_machine_keeps_its_messages_bounded_with_a_memory():
    bounded = _payload_sizes(memory=2)
    unbounded = _payload_sizes(memory=None)

    # the states and the count of forgotten transitions take more digits, not more entries
    assert max(bounded) <= min(bounded) + 4
    assert unbounded[-1] > 2 * unbounded[9]


def test_collective_state_machine_agrees_after_many_transitions_with_a_memory():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    def transition(state):
        if sense("source") and state < 20 and counter() >= 2:
            return state + 1
        return state

    @aggregate
    def program():
        return collective_state_machine(0, transition, memory=2)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(60)

    assert _states(simulator) == [20] * 5


def test_collective_state_machine_rejects_a_memory_shorter_than_a_transition():
    with pytest.raises(ValueError):
        Device(0, lambda: collective_state_machine(0, lambda state: state, memory=0)).run_round({})


def test_collective_state_machine_returns_the_state_its_transition_ran_on():
    ran_on = {}

    def program():
        def transition(state):
            ran_on[local_id()] = state
            return Next(WANDER, 0.0) if sense("source") else state
        return collective_state_machine(WAIT, transition)

    devices = [Device(0, program), Device(1, program)]
    for _ in range(3):
        payloads = [device.run_round({"source": device.device_id == 0}) for device in devices]
        devices[0].receive(1, payloads[1])
        devices[1].receive(0, payloads[0])
        assert [device.result for device in devices] == [ran_on[0], ran_on[1]]

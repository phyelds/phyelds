from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import Next, collective_state_machine
from phyelds.libraries.device import sense
from phyelds.libraries.time import counter
from phyelds.vm.device import Device
from phyelds.simulator.runner import schedule_program_for_all
from tests.libraries.simulator_utils import setup_up_simulator


def _states(simulator) -> list:
    return [node.data["result"] for node in simulator.environment.nodes.values()]


def _run(simulator, transition, rounds: int = 10):
    @aggregate
    def program():
        return collective_state_machine("idle", transition)

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(rounds)


def test_collective_state_machine_spreads_a_transition_proposed_by_one_device():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    # "active" < "idle": a transition wins over staying whatever the order of the states
    _run(simulator, lambda state: "active" if sense("source") else state)

    assert _states(simulator) == ["active"] * 5


def test_collective_state_machine_settles_a_conflict_with_the_higher_priority():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[4].data["target"] = True

    def transition(state):
        if state == "idle" and sense("source"):
            return "explore"
        if state == "idle" and sense("target"):
            return Next("defend", priority=1.0)
        return state

    _run(simulator, transition)

    assert _states(simulator) == ["defend"] * 5


def test_collective_state_machine_settles_a_conflict_of_equal_priority_with_the_greater_state():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[4].data["target"] = True

    def transition(state):
        if state == "idle" and sense("source"):
            return "explore"
        if state == "idle" and sense("target"):
            return "defend"
        return state

    _run(simulator, transition)

    assert _states(simulator) == ["explore"] * 5


def test_collective_state_machine_runs_each_state_on_its_own_alignment():
    # Without alignment, the counter of "idle" would go on counting in "busy".
    def transition(state):
        if counter() < 3:
            return state
        return "busy" if state == "idle" else "idle"

    device = Device(0, lambda: collective_state_machine("idle", transition))
    states = []
    for _ in range(9):
        device.run_round({})
        states.append(device.result)

    assert states == ["idle", "idle", "busy", "busy", "busy", "idle", "idle", "idle", "busy"]


def test_collective_state_machine_agrees_over_messages_sent_as_bytes():
    def program():
        return collective_state_machine("idle", lambda state: "active" if sense("source") else state)

    devices = [Device(0, program), Device(1, program)]
    for _ in range(3):
        payloads = [device.run_round({"source": device.device_id == 0}) for device in devices]
        devices[0].receive(1, payloads[1])
        devices[1].receive(0, payloads[0])

    assert [device.result for device in devices] == ["active", "active"]

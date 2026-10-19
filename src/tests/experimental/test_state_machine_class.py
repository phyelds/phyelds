import math
from enum import Enum

import pytest

from phyelds.calculus import aggregate
from phyelds.experimental.state_machines import StateMachine
from phyelds.libraries.device import sense
from phyelds.libraries.time import counter
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.device import Device
from tests.libraries.simulator_utils import setup_up_simulator


def _results(simulator) -> list:
    return [node.data["result"] for node in simulator.environment.nodes.values()]


def _run(simulator, machine: StateMachine, rounds: int = 10) -> list:
    @aggregate
    def program():
        return machine.run()

    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(rounds)
    return _results(simulator)


def _alarm_machine() -> StateMachine:
    machine = StateMachine("idle", "active")

    @machine.state("idle", to=["active"])
    def idle():
        if sense("source"):
            machine.go("active")
        return 0

    @machine.state("active")
    def active():
        return counter()

    return machine


def test_state_machine_starts_in_its_first_state_and_returns_its_output():
    results = _run(setup_up_simulator(3), _alarm_machine())

    assert results == [("idle", 0)] * 3


def test_state_machine_spreads_a_transition_and_runs_the_new_state():
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True

    results = _run(simulator, _alarm_machine())

    assert [state for state, _ in results] == ["active"] * 5
    assert all(rounds > 0 for _, rounds in results)


def test_state_machine_settles_conflicts_by_priority_then_by_the_later_state():
    machine = StateMachine("idle", "explore", "rescue", "defend")

    @machine.state("idle")
    def idle():
        if sense("source"):
            machine.go("rescue")
        if sense("target"):
            machine.go("explore", priority=math.inf)

    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].data["source"] = True
    simulator.environment.nodes[2].data["target"] = True
    simulator.environment.nodes[4].data["source"] = True

    assert [state for state, _ in _run(simulator, machine)] == ["explore"] * 5


def test_state_machine_keeps_the_winning_transition_when_a_state_proposes_more():
    machine = StateMachine("idle", "explore", "defend")

    @machine.state("idle")
    def idle():
        machine.go("defend", priority=1.0)
        machine.go("explore")

    assert _run(setup_up_simulator(1), machine) == [("defend", None)]


def test_state_machine_stays_in_a_state_without_a_function():
    machine = StateMachine("idle", "done")

    @machine.state("idle")
    def idle():
        machine.go("done")

    assert _run(setup_up_simulator(2), machine) == [("done", None)] * 2


def test_state_machine_agrees_over_messages_sent_as_bytes():
    machine = _alarm_machine()
    devices = [Device(0, machine.run), Device(1, machine.run)]
    for _ in range(4):
        payloads = [device.run_round({"source": device.device_id == 0}) for device in devices]
        devices[0].receive(1, payloads[1])
        devices[1].receive(0, payloads[0])

    assert [device.result[0] for device in devices] == ["active", "active"]


def test_state_machine_rejects_a_transition_to_a_state_it_does_not_declare():
    machine = StateMachine("idle", "active", "done")

    @machine.state("idle", to=["active"])
    def idle():
        machine.go("done")

    with pytest.raises(ValueError):
        Device(0, machine.run).run_round({})


@pytest.mark.parametrize("states", [(), ("idle", "idle")])
def test_state_machine_rejects_no_states_or_repeated_ones(states):
    with pytest.raises(ValueError):
        StateMachine(*states)


def test_state_machine_rejects_an_unknown_state():
    machine = StateMachine("idle")

    with pytest.raises(ValueError):
        machine.state("busy")
    with pytest.raises(ValueError):
        machine.state("idle", to=["busy"])


def test_state_machine_rejects_go_outside_a_state():
    with pytest.raises(RuntimeError):
        StateMachine("idle", "active").go("active")


def test_state_machine_draws_its_declared_transitions_as_mermaid():
    assert _alarm_machine().to_mermaid() == "\n".join([
        "stateDiagram-v2",
        "    [*] --> idle",
        "    idle --> active",
    ])


def test_state_machine_takes_the_members_of_an_enum_as_states():
    class Phase(Enum):
        IDLE = "i"
        ACTIVE = "a"

    machine = StateMachine(*Phase)

    @machine.state(Phase.IDLE, to=[Phase.ACTIVE])
    def idle():
        machine.go(Phase.ACTIVE)

    assert _run(setup_up_simulator(2), machine) == [(Phase.ACTIVE, None)] * 2
    assert machine.to_mermaid().splitlines()[1:] == ["    [*] --> IDLE", "    IDLE --> ACTIVE"]


def test_state_machine_stays_rather_than_going_to_an_earlier_state_with_the_lowest_priority():
    # Remark 1: the program produces the maximum of staying and of its transitions.
    machine = StateMachine("idle", "busy")

    @machine.state("idle")
    def idle():
        machine.go("busy")

    @machine.state("busy")
    def busy():
        machine.go("idle")

    assert _run(setup_up_simulator(1), machine) == [("busy", None)]

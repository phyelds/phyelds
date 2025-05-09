"""
This module contains the event to run the aggregate program in the simulator
"""
from phyelds import engine
from phyelds.data import State
from phyelds.simulator import Simulator, Node


def aggregate_program_runner(
    simulator: Simulator, time_delta: float, node: Node, program: callable
):
    """
    Run the program for a node.
    """
    # get neighbors
    all_neighbors = simulator.environment.get_neighbors(node)
    # take the messages from the neighbors, create a dict like id -> messages (that is a dict)
    neighbors_messages = {
        neighbor.id: neighbor.data.get("messages", {}) for neighbor in all_neighbors
    }
    engine.setup(node.id, neighbors_messages, node.data.get("state", {}))
    result = program(node)
    if isinstance(result, State):
        result = result.value
    node.data["result"] = result
    node.data["messages"] = engine.cooldown()
    node.data["state"] = engine.state_trace()
    simulator.schedule_event(
        time_delta, aggregate_program_runner, simulator, time_delta, node, program
    )

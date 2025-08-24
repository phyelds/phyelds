"""Minimal simulation example for phyelds.
"""
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.simulator.neighborhood import full_neighborhood


@aggregate
def neighbor_count():
    """
    Each node advertises the value 1; summing counts (neighbors + self)
    """
    c = remember(0).update_fn(lambda x: x + 1)  # each device keeps its own counter
    nbr_c = neighbors(c)                  # gather neighbor counters (and self)
    # Simple average of all visible counters
    return sum(nbr_c) / len(nbr_c.data)


def main():
    """
    A simple simulation of neighbor counting and state management.
    """
    sim = Simulator()
    # create 5 devices in a line
    for i in range(5):
        sim.create_node((i, 0), node_id=i)

    schedule_program_for_all(sim, 1.0, neighbor_count)
    sim.environment.set_neighborhood_function(full_neighborhood)
    sim.run(5)

    for node in sim.environment.nodes.values():
        print(f"Node {node.id} sees {node.data['result']} devices (including itself)")


if __name__ == "__main__":
    main()

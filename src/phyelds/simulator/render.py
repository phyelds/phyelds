"""
Render the nodes in the simulator's environment.
"""

from typing import Tuple

from matplotlib import pyplot as plt

from phyelds.simulator import Simulator


class Link:
    """
    A class to represent a link between two nodes.
    The link is represented as a tuple of two nodes.
    Note!
    Link(node1, node2) == Link(node2, node1)
    """

    def __init__(self, node1: Tuple[float, ...], node2: Tuple[float, ...]):
        self.node1 = node1
        self.node2 = node2

    def __hash__(self):
        return hash(frozenset((self.node1, self.node2)))

    def __eq__(self, other):
        if isinstance(other, Link):
            return frozenset((self.node1, self.node2)) == frozenset(
                (other.node1, other.node2)
            )
        return False


def render_sync(simulator: Simulator, color_from: str = None):
    """
    Render the nodes in the simulator's environment.
    """
    positions = [node.position for node in simulator.environment.nodes.values()]
    x, y = zip(*positions)
    # plot also the neighbors, avoiding duplicates
    all_neighbors_tuple = set()
    for node in simulator.environment.nodes.values():
        neighbors = node.get_neighbors()
        for neighbor in neighbors:
            all_neighbors_tuple.add(Link(node.position, neighbor.position))
    for link in all_neighbors_tuple:
        plt.plot(
            [link.node1[0], link.node2[0]],
            [link.node1[1], link.node2[1]],
            "r--",
            alpha=0.1,
        )
    # take the colors from the node data
    if color_from:
        colors = [
            node.data.get(color_from, "blue")
            for node in simulator.environment.nodes.values()
        ]
        plt.scatter(x, y, c=colors)
    else:
        plt.scatter(x, y, c="blue")
    # Add node IDs as text labels
    for node in simulator.environment.nodes.values():
        plt.text(
            node.position[0] + 0.02,
            node.position[1],
            str(node.id),
            fontsize=8,
            ha="center",
            va="center",
            bbox={"facecolor": "white", "alpha": 0.1, "edgecolor": "none"},
        )
    plt.title("Node Positions")
    plt.xlabel("X Position")
    plt.ylabel("Y Position")
    plt.axis("equal")
    plt.show()
    simulator.schedule_event(
        1.0, render_sync, simulator, color_from
    )  # Schedule next render

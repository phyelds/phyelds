"""
A group of functions based on the notion of time.
"""
from phyelds import engine
<<<<<<< HEAD
from phyelds.calculus import aggregate, remember_and_evolve
=======
from phyelds.calculus import aggregate, remember_and_evolve, remember
>>>>>>> feat/vmas-integration
from phyelds.data import StateT


def local_time() -> float:
    """
    Get the local time of the node.
    :return: the local time of the node.
    """
    return engine.get().node_context.time()


@aggregate
def counter() -> StateT[int]:
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)

@aggregate
def decay(value: float | int, rate: float | int) -> StateT[float | int]:
    """
    Apply a decay function to a value
    :param value: the initial value
    :param rate: the decay rate
    :return: the decayed value
    """
    set_value, decay_value = remember(value)
    print(decay_value)
    if decay_value > 0:
        set_value(max(0, decay_value - rate))
    return decay_value
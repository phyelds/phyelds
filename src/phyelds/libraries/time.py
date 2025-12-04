"""
A group of functions based on the notion of time.
"""
from phyelds import engine
from phyelds.calculus import aggregate, remember_and_evolve
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

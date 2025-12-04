import timeit

from phyelds import engine
from phyelds.calculus import aggregate, remember, neighbors, remember_and_evolve
from phyelds.internal import MutableEngine
from tests.calculus.mock import MockNodeContext, MockSimulator


def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))

@aggregate
def counter():
    """
    Simple counter function that counts the number of times it is called.
    :return: a counter that counts the number of times it is called.
    """
    return remember_and_evolve(0, lambda x: x + 1)

@aggregate
def depth_check(n):
    if n == 0:
        return counter()
    else:
        counter()
        depth_check(n - 1)

@aggregate
def neighbors_check():
    return neighbors(1)

def remember_depth_bench(depth_count):
    MutableEngine().setup(MockNodeContext(0))
    depth_check(depth_count)

def remember_same_level_bench(calls):
    MutableEngine().setup(MockNodeContext(0))
    for _ in range(calls):
        counter()

if __name__ == "__main__":
    setup_engine()
    depths = [1, 5, 10, 20, 40]
    numbers = 1000

    with open("benchmark_results.csv", "w") as results_file:
        # Write CSV headers
        results_file.write("benchmark_type,parameter,time_seconds,throughput_ops_per_second\n")

        # Depth benchmark
        for depth in depths:
            result = timeit.timeit(lambda: remember_depth_bench(depth), number=numbers)
            throughput = numbers / result
            results_file.write(f"depth,{depth},{result:.5f},{throughput:.5f}\n")

        # Same level calls benchmark
        calls = depths
        for call in calls:
            result = timeit.timeit(lambda: remember_same_level_bench(call), number=numbers)
            throughput = numbers / result
            results_file.write(f"same_level,{call},{result:.5f},{throughput:.5f}\n")

        # Neighbors benchmark
        neighbors_count = depths
        for neighbor in neighbors_count:
            simulator = MockSimulator(neighbor)
            result = timeit.timeit(lambda: simulator.cycle(neighbors_check), number=numbers)
            result = result / neighbor
            throughput = numbers / result
            results_file.write(f"neighbors,{neighbor},{result:.5f},{throughput:.5f}\n")
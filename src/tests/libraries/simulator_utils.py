from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood


def setup_up_simulator(size):
    simulator = Simulator()
    grid_generation(simulator, size, 1, spacing=1)
    simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))
    simulator.environment.add_data_for_all_nodes({"source": False})
    return simulator
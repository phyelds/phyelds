# set random seed
import random

from fieldpy.calculus import aggregate, neighbors_distances
from fieldpy.libraries.collect import collect_or
from fieldpy.libraries.diffusion import distance_to
from fieldpy.simulator import Simulator
from fieldpy.simulator.deployments import deformed_lattice
from fieldpy.simulator.neighborhood import radius_neighborhood
from fieldpy.simulator.render import render_sync
from fieldpy.simulator.runner import aggregate_program_runner

random.seed(42)


@aggregate
def main(context):
    distances = neighbors_distances(context.position)
    target_distance = distance_to(context.data["target"], distances)
    nodes_in_path = collect_or(context, target_distance, context.data["source"])
    # distance from nodes_in
    distance_from_path = distance_to(nodes_in_path, distances)
    channel = 1.0 if distance_from_path < 0.12 else 0.0
    return channel  # distance_to(leader == 33, distances)


simulator = Simulator()
# deformed lattice
simulator.environment.set_neighborhood_function(radius_neighborhood(0.12))
deformed_lattice(simulator, 20, 20, 0.1, 0.01)
# put source
for node in simulator.environment.nodes.values():
    node.data = {"source": False, "target": False}
# put a source in the first node
simulator.environment.node_list()[0].data["source"] = True
target = simulator.environment.node_list()[-1]
target.data["target"] = True
# schedule the main function
for node in simulator.environment.nodes.values():
    simulator.schedule_event(0.0, aggregate_program_runner, simulator, 0.1, node, main)
# render
simulator.schedule_event(1.0, render_sync, simulator, "result")
simulator.run(100)

"""
A phyelds program on the agents of a Mesa model.

Agents wander in a square; each one computes, with phyelds, how many radio hops it is
from the first agent, the source. Needs ``pip install phyelds-mesa``.

    poetry run python docs/examples/mesa_swarm.py
"""
import math

import mesa
import numpy as np
from mesa.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent

from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.mesa import AggregateRuntime, within


# --8<-- [start:model]
@aggregate
def hops_to_source():
    """Hops to the source; agents that cannot reach it store that they are cut off."""
    hops = distance_to(sense("source"), hops_distance())
    store("cut_off", hops == math.inf)
    return hops


class Swarm(mesa.Model):
    """Agents wandering in the unit square, with a phyelds field on top."""

    def __init__(self, agents: int = 30, radius: float = 0.3, speed: float = 0.02, seed: int = 42):
        super().__init__(rng=seed)
        self.speed = speed
        space = ContinuousSpace([[0, 1], [0, 1]], torus=False, random=self.random, n_agents=agents)
        for _ in range(agents):
            ContinuousSpaceAgent(space, self).position = self.rng.random(2)
        self.source = self.agents[0]
        self.runtime = AggregateRuntime(
            hops_to_source,
            neighbors=within(radius),
            sensors=lambda agent: {"source": agent is self.source},
        )
        self.hops: dict[int, float] = {}

    def step(self):
        for agent in self.agents:
            move = self.rng.uniform(-self.speed, self.speed, 2)
            agent.position = np.clip(agent.position + move, 0.0, 1.0)
        self.hops = self.runtime.run_round(self.agents)  # one round of phyelds per step
# --8<-- [end:model]


def main() -> None:
    """Run the swarm and print the hops of each agent."""
    model = Swarm()
    for _ in range(50):
        model.step()
    cut_off = sum(outputs["cut_off"] for outputs in model.runtime.outputs.values())
    print({agent_id: hops for agent_id, hops in sorted(model.hops.items())})
    print(f"{cut_off} agents cannot reach the source")


if __name__ == "__main__":
    main()

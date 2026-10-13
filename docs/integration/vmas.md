# Case study: VMAS

[VMAS](https://github.com/proroklab/VectorizedMultiAgentSimulator) is a vectorised
multi-robot simulator. The `phyelds-vmas` package connects it to phyelds by reusing
the bundled simulator, so it is a compact example of the
"[custom environment](index.md#two-ways-to-integrate)" approach.

```bash
pip install phyelds-vmas
```

## How it works

- **`VmasEnvironment`** is an `Environment` whose nodes mirror the VMAS agents:
  `initialize_nodes` creates one node per agent, and `update_nodes` copies, after
  every VMAS step, each agent's position, observations, reward and done flag into
  the node. To the program they are ordinary sensors: `sense("observations")`.
- **`vmas_runner`** is a recurring simulator event: it reads the `action` output that
  each program `store`d, steps VMAS with all the actions at once, updates the nodes
  and schedules itself again.
- The aggregate program runs with the usual `schedule_program_for_all`.

```python
from vmas import make_env

from phyelds.calculus import aggregate
from phyelds.libraries.device import store
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, vmas_runner

environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1))
simulator = Simulator(environment)

@aggregate
def move_right():
    store("action", [1, 0])

schedule_program_for_all(simulator, 0.0, 1.0, move_right)
simulator.schedule_event(0.2, vmas_runner, simulator, 1.0)   # VMAS steps after the programs
simulator.run(10)
```

The offset of `vmas_runner` (0.2 here) makes sure every device has run its round,
and stored its action, before VMAS steps.

The same pattern fits any host that can be stepped from Python: map the host's
entities to nodes, its readings to node data, and the programs' outputs to the
host's actions.

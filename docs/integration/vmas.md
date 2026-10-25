# Case study: VMAS

[VMAS](https://github.com/proroklab/VectorizedMultiAgentSimulator) is a vectorised
multi-robot simulator. The `phyelds-vmas` package connects it to phyelds by reusing
the phyelds simulator, so it is a compact example of the
"[custom environment](index.md#ways-to-integrate)" approach.

```bash
pip install phyelds-vmas
```

## How it works

- **`VmasEnvironment`** is an `Environment` whose nodes mirror the VMAS agents:
  `initialize_nodes` creates one node per agent, and `update_nodes` copies, after
  every VMAS step, each agent's position, observations, reward and done flag into
  the node. Programs read them through typed sensors: `observations.sense()`.
- **`vmas_runner`** is a recurring simulator event: it reads the `action` output that
  each program sent through `action.send(...)`, steps VMAS with all the actions at once, updates the nodes
  and schedules itself again.
- The aggregate program runs with the usual `schedule_program_for_all`.

The host and programs share these objects from `phyelds.vmas`:

| Object | Value returned by `.sense()` |
| --- | --- |
| `observations` | The agent's observation tensor |
| `rewards` | A scalar reward tensor, initially zero |
| `dones` | A Python `bool` indicating episode completion, initially `False` |
| `infos` | A dictionary of info tensors, initially `{}` |
| `agent` | The VMAS `Agent` object |

Readings and node positions select environment 0, including every info tensor's
first batch entry. The `Agent` object retains its batched state. If VMAS has
multiple environments, the runner repeats each agent's action across them.
The sensor value types stay the same after a step. The original names still
work with `sense("observations")` or `store("action", ...)`.

`action.send(...)` accepts the action defined by the scenario, such as a force
vector or a discrete choice; it is distinct from the core `velocity` actuator.

```python
from vmas import make_env

from phyelds.calculus import aggregate
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, action, vmas_runner

environment = VmasEnvironment(make_env(scenario="flocking", num_envs=1))
simulator = Simulator(environment)

@aggregate
def move_right():
    action.send([1, 0])

schedule_program_for_all(simulator, 0.0, 1.0, move_right)
simulator.schedule_event(0.2, vmas_runner, simulator, 1.0)   # VMAS steps after the programs
simulator.run(10)
```

The offset of `vmas_runner` (0.2 here) makes sure every device has run its round,
and sent its action, before VMAS steps. Each program must send an action on every
round. If a node has not run yet or its latest round sent no action, the runner
raises a `ValueError` naming that node before stepping VMAS.

The same pattern fits any host that can be stepped from Python: map the host's
entities to nodes, its readings to node data, and the programs' outputs to the
host's actions.

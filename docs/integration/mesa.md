# Mesa

[Mesa](https://mesa.readthedocs.io) is a framework for agent-based models in Python.
The `phyelds-mesa` package runs phyelds programs on the agents of a Mesa model: Mesa
moves the agents, phyelds computes fields on top of them.

```bash
pip install phyelds-mesa
```

It installs a compatible phyelds release and Mesa.

---

## How it works

`phyelds.mesa.AggregateRuntime` is a host that follows [the round
protocol](index.md#the-round-protocol), with Mesa agents as devices:

- **Devices**: each agent is a device, identified by its `unique_id`.
- **Rounds**: `run_round(agents)` runs the program once on each agent, and returns its
  results by `unique_id`. Call it from the `step` of the model.
- **Synchronous rounds**: in a round every agent receives what its neighbors sent in the
  previous round, so the order of the agents does not matter.
- **Neighbors**: a function of the agent decides who it talks to.
  - `within(radius)`: the agents closer than `radius` in a continuous space.
  - `cell_neighbors`: the other agents in the same cell and in its neighborhood, in a
    grid or a network.
  - Any function from an agent to agents, for instance to cut the links that cross a wall.
- **Sensors**: every agent senses `position` (its position, or the coordinate of its
  cell) and `time` (the time of the model). `sensors=` adds more, from a function of the
  agent.
- **Outputs**: what the program `store`s is in `runtime.outputs`, by `unique_id`.
- **Agents that leave**: an agent missing from a round is forgotten, with its state
  and its messages.

---

## Example

Agents wander in a square, and each one computes how many radio hops it is from the
source:

```python
--8<-- "mesa_swarm.py:model"
```

The complete example is
[`docs/examples/mesa_swarm.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/mesa_swarm.py).

---

## Notes

- **Messages are shared, not copied**: as in the phyelds simulator, an agent receives the
  very objects its neighbors sent. Never mutate a value received from a neighbor (see
  [common pitfalls](../pitfalls.md)).
- **One runtime per program**: a runtime keeps the state of its program on each agent.
  To run two independent programs, use two runtimes. `reset()` forgets everything, for
  instance between episodes.

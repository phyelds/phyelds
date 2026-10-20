# Experimental

`phyelds.experimental` holds the studies in progress: ideas we are still trying out, to
understand how they fit phyelds and what their API should look like.

!!! warning "Not a stable API"
    What lives here works and is tested, but it **will probably change**, and it may
    change in any release, minor ones included, without a deprecation period. Pin the
    version of phyelds if you depend on it. When a study settles, it moves to the
    [standard libraries](../concepts/libraries.md).

## Studies

| Study | Module | What it does |
| --- | --- | --- |
| [Collective state machines](state-machines.md) | `phyelds.experimental.state_machines` | A finite state machine run by the whole network, whose transitions are collective agreements |
| [Swarm behaviours](swarm.md) | `phyelds.experimental.swarm` | Blocks that compute where a robot moves, to sum and weigh: flocking, following a leader, teams |
| [Formations](formations.md) | `phyelds.experimental.formation` | A swarm spreads evenly over a shape, a signed distance function, with or without positions |

# Benchmarks

How hosts, their adapters and phyelds scale with many agents in one world. The harness
lives outside the pytest `testpaths`, so CI does not run it.

```bash
poetry run python benchmarks/run.py --hosts simulator mesa --nodes 100 1000 > results.jsonl
poetry run python benchmarks/run.py --hosts vmas --nodes 100 >> results.jsonl
poetry run python benchmarks/run.py --hosts argos --nodes 1000 10000 --rounds 50 >> results.jsonl
poetry run python benchmarks/run.py --hosts webots --nodes 100 --rounds 500 >> results.jsonl
```

Each line of the output is one measurement, made in a process of its own. A measurement
that fails gives a line with an `error` instead of the metrics.

## What varies

- **Hosts**: `simulator`, `mesa` (`phyelds-mesa`), `vmas` (`phyelds-vmas` on the
  flocking scenario, without obstacles), `argos` (`phyelds-argos`, foot-bots) and `webots`
  (`phyelds-webots`, one process per robot). The extensions are found from their sources.
- **Agents** (`--nodes`), on a square grid with some jitter (`--seed`). Every agent runs
  phyelds, except at the `none` stage, and the world is one.
- **Layout**: at constant `density`, the area grows with the agents and each one has about
  `--degree` neighbors within a radius of 1. At constant `area`, the area is that of
  `--area-nodes` agents, so the density grows with the agents.
- **Stage**: `none` runs the host alone, `empty` adds the adapter with a program that does
  nothing, and `gradient`, `gossip` and `count` run the programs of `programs.py`
  (`distance_to`, `gossip_max` and `count_nodes`).

## What is measured

| Field | Meaning |
|---|---|
| `agent_rounds_per_s` | Rounds of all the agents per second of wall time |
| `sim_over_wall` | Simulated time over wall time |
| `rss_peak_mb` | Peak resident memory of the measurement, or of its largest child process |
| `neighbor_search_s` | One neighbor search for every agent, timed on its own |
| `messages_per_round` | Messages delivered in a round (simulator, Mesa and VMAS) |
| `bytes_per_round` | Encoded size of the last round's messages (simulator and VMAS) |
| `startup_s` | Start-up of the hosts that run in processes of their own |
| `environment` | Versions, processor, memory, operating system and commit |

## Limits

- Pin the measurements to the same kind of core, e.g. `taskset -c 2 poetry run python
  benchmarks/run.py ...`. On processors with cores of different speeds, a measurement that
  is not pinned can land on either. The `environment` records the CPUs the measurement could
  use.
- ARGoS and Webots run in processes of their own. Their time is that of `--rounds` rounds
  less that of one, which leaves the start-up out. With few agents or rounds the start-up
  noise is larger than the difference, so give them hundreds of rounds.
- ARGoS has no `none` stage, as its robots need a controller.
- VMAS on its own, at the `none` stage, takes tens of seconds a step with 1,000 agents of the
  flocking scenario, so measure it up to 100.
- Webots starts a Python process for each robot, which caps it at a few hundred robots
  on one machine.
- The simulator's `radius_neighborhood` scans every node for every node, which makes a
  round O(N²). At 10,000 agents a round mostly measures that scan, as `neighbor_search_s`
  shows.

## Baseline

The [benchmarks page](https://phyelds.github.io/phyelds/integration/benchmarks/) of the docs
charts the baseline and lists every measurement, with the machine it ran on. The
measurements are in `baseline.jsonl`; `poetry run python docs/examples/benchmarks.py`
redraws the charts from them.

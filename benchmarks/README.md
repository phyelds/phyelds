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

Agent-rounds per second at each stage, on phyelds 9.3.1 with the default `--seed`,
`--degree` and `--area-nodes` (1, 8 and 1,000).

| Host | Agents | Layout | none | empty | gradient | gossip | count | Neighbor search (s) | Messages/round | Peak RSS (MB) |
|---|---|---|---|---|---|---|---|---|---|---|
| simulator | 100 | density | 1,404,189 | 18,861 | 13,982 | 16,788 | 8,995 | 0.00448 | 636 | 30 |
| simulator | 100 | area | 2,003,141 | 25,914 | 16,418 | 17,356 | 10,209 | 0.00317 | 0 | 30 |
| simulator | 1,000 | density | 1,711,147 | 2,991 | 2,722 | 2,784 | 2,384 | 0.321 | 7,132 | 66 |
| simulator | 1,000 | area | 1,701,175 | 2,979 | 2,726 | 2,782 | 2,387 | 0.321 | 7,132 | 66 |
| simulator | 10,000 | density | 1,253,494 | 274 | 280 | 282 | 279 | 36.7 | 72,768 | 114 |
| simulator | 10,000 | area | 1,352,495 | 285 | 276 | 274 | 267 | 35.4 | 749,840 | 114 |
| mesa | 100 | density | 14,119,906 | 108,815 | 24,000 | 28,383 | 11,626 | 0.000594 | 636 | 120 |
| mesa | 100 | area | 12,526,619 | 121,326 | 27,769 | 32,265 | 13,901 | 0.000536 | 0 | 121 |
| mesa | 1,000 | density | 134,266,045 | 65,026 | 20,420 | 22,689 | 10,288 | 0.0102 | 7,132 | 129 |
| mesa | 1,000 | area | 126,027,122 | 66,624 | 19,774 | 23,198 | 10,270 | 0.0103 | 7,132 | 129 |
| mesa | 10,000 | density | 964,273,639 | 12,598 | 8,317 | 9,021 | 5,845 | 0.741 | 72,768 | 210 |
| mesa | 10,000 | area | 954,872,705 | 11,306 | 6,517 | 7,096 | 3,628 | 0.783 | 749,840 | 210 |
| vmas | 100 | density | 411 | 406 | 397 | 398 | 389 | 0.00328 | 636 | 230 |
| vmas | 100 | area | 413 | 403 | 397 | 396 | 391 | 0.00333 | 0 | 230 |
| argos | 100 | density | — | 41,657 | 13,693 | 16,704 | 6,998 | — | — | 51 |
| argos | 100 | area | — | 63,600 | 21,708 | 24,677 | 10,303 | — | — | 50 |
| argos | 1,000 | density | — | 28,019 | 11,512 | 13,428 | 6,113 | — | — | 113 |
| argos | 1,000 | area | — | 29,027 | 11,567 | 13,534 | 6,287 | — | — | 114 |
| argos | 10,000 | density | — | 15,445 | 9,039 | 7,650 | 4,365 | — | — | 752 |
| webots | 100 | density | — | 20,959 | 10,931 | 11,433 | 6,837 | — | — | 300 |
| webots | 100 | area | — | 23,403 | 12,355 | 12,388 | 9,009 | — | — | 300 |

- Machine: AMD Ryzen AI 9 HX PRO 370 with 30 GB, Linux 7.0, Python 3.13.2; Mesa 3.5.1,
  VMAS 1.5.2 with PyTorch 2.5.1 on the CPU, ARGoS 3 and Webots R2025a.
- Each measurement ran on one Zen 5 core (`taskset -c 2`); Webots, which runs a process
  per robot, on the eight Zen 5 CPUs (`taskset -c 0-3,12-15`).
- Rounds: 10 for the simulator, Mesa and VMAS (2 for the simulator at 10,000), 100 for
  ARGoS (60 at 10,000) and 500 for Webots.
- At 100 agents, the `area` layout spreads them over the area of 1,000, out of each other's
  range, so they exchange no messages; at 1,000 the two layouts are the same.
- ARGoS at 10,000 is measured at constant density only: it takes about 5 minutes to start
  10,000 foot-bots spread out, and over half an hour packed in the area of 1,000.
- Webots alone runs 500 rounds in less time than it takes to start, so its `none` stage
  has no figure.

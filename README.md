<div align="center">

# Phyelds

Lightweight, pythonic aggregate computing & field calculus toolkit for building, simulating, and experimenting with decentralized adaptive systems.

[![PyPI version](https://img.shields.io/pypi/v/phyelds.svg)](https://pypi.org/project/phyelds/)
[![Python versions](https://img.shields.io/pypi/pyversions/phyelds.svg)](https://pypi.org/project/phyelds/)
[![License](https://img.shields.io/github/license/phyelds/phyelds.svg)](./LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/phyelds/phyelds.svg)](https://github.com/phyelds/phyelds)

</div>

---

## Table of Contents

- [Why phyelds?](#why-phyelds)
- [Features](#features)
- [Installation](#installation)
- [Core Concepts](#core-concepts)
  - [Local State (`remember`)](#1-local-state-remember)
  - [Neighborhood Values (`neighbors`)](#2-neighborhood-values-neighbors)
  - [Combine State + Neighborhood](#3-combine-state--neighborhood)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Running a Minimal Simulation](#running-a-minimal-simulation)

---

## Why phyelds?

You write one program describing global behaviour; all devices run it, exchanging only neighbor information. The library stays minimal so you can read the code and experiment quickly.

## Features

* Core primitives: `@aggregate`, `remember`, `neighbors`.
* Functional `Field` abstraction (arithmetic & iteration) for neighbor values.
* Pluggable discrete‑event simulator for experiments.
* Extra libraries (spreading, collection, gossip, leader election) built on the same core.

## Installation

```bash
pip install phyelds        # from PyPI
# or
poetry add phyelds
```

From source:

```bash
git clone https://github.com/phyelds/phyelds.git
cd phyelds
pip install -e .
```

Requires Python 3.13+ (see `pyproject.toml`).

## Core Concepts
To build spatio‑temporal (global) programs in Phyelds you only need a few simple ideas: every device runs the same `@aggregate` function in discrete *rounds*,
local persistent state is managed with `remember(...)`,
and devices exchange values with neighbors to form `Field`s.
The table below summarizes these core primitives and their intuition.

| Primitive | What it does | Intuition |
|-----------|--------------|-----------|
| `@aggregate` | Marks a function executed each round on every device. | Single spec, many instances. |
| `remember(init)` | Persistent local state across rounds. | Local variable that survives. |
| `neighbors(value)` | Collects one value from each neighbor (and self) into a `Field`. | One communication hop. |
| `Field` | Iterable mapping (id → value) with element‑wise ops. | Lightweight vector of neighbor data. |


**Practical tips:**
* Treat rounds as atomic: reading remember().value gives last round's state.
* Keep aggregate functions deterministic and side‑effect free for easier reasoning and testing.
* Start small: use remember + neighbors examples above to experiment before adding the simulator.

In the next section we'll explore these core concepts in more detail with practical examples.

### 1. Local State (`remember`)

```python
from phyelds.calculus import aggregate, remember

@aggregate
def counter():
    # Starts at 0 the first round, then increments each subsequent round
    update_counter, counter_value = remember(0)
    update_counter(counter_value + 1)
    return counter_value
```
**Idea:** `remember` gives you a mutable state cell; `.update_fn` rewrites it each round.

### 2. Neighborhood Values (`neighbors`)

```python
from phyelds.calculus import aggregate, neighbors

@aggregate
def neighbor_sum():
    # Every device advertises the constant 1; result = number of (neighbors + self)
    nbr = neighbors(1)
    return sum(nbr)
```
**Idea:** Calling `neighbors(v)` both sends `v` out and returns a `Field` of received values (including self), so summing counts devices in the local neighborhood plus self.

### 3. Combine State + Neighborhood

```python
from phyelds.calculus import aggregate, remember_and_evolve, neighbors

@aggregate
def average_counter():
    # Each node advertises the value 1; summing counts (neighbors + self)
    c = remember_and_evolve(0, lambda x: x + 1)  # each device keeps its own counter
    nbr_c = neighbors(c)                  # gather neighbor counters (and self)
    # Simple average of all visible counters
    return sum(nbr_c) / len(nbr_c.data)
```
**Idea:** Persist something locally, exchange it, compute a derived aggregate.

That is the core. Everything more advanced (gradients, collection trees, leader election) is constructed from these.

## Development

```bash
git clone https://github.com/phyelds/phyelds.git
cd phyelds
poetry install
poetry run pytest -q
```

## Contributing

1. Open an issue for non‑trivial changes.
2. Keep PRs focused with tests.
3. Run linters & tests before submitting.

## License

Apache License 2.0 – see [LICENSE](./LICENSE).

---

## Running a Minimal Simulation

A runnable example is provided in `src/minimal_simulation.py`.

Run it:

```bash
poetry run python src/minimal_simulation.py
```

It creates 5 nodes in a line, each advertising `1`, and prints how many devices each node sees (neighbors + itself). Interior nodes report 3; endpoints report 2.

---

Happy field building! ✨

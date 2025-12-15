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
* `NeighborhoodField` abstraction (arithmetic & iteration) for neighbor values.
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

Requires Python 3.12+ (see `pyproject.toml`).

## Core Concepts

Phyelds is rooted in the aggregate computing paradigm, where the main idea is based on the concept of computational fields: a distributed data structure representing values spread over space and time. This data cannot be directly manipulated from a single device, but is instead constructed through local interactions and repeated interpretation of the same program by all devices in the system.

For more details, please refer to the [main paper on aggregate computing](https://www.sciencedirect.com/science/article/pii/S235222081930032X).

Most current incarnations of aggregate computing follow a functional programming style, where the operators are stateless and side-effect free.
*Phyelds* tries to be more pragmatic and Pythonic, allowing some controlled mutability and side effects while still keeping the core ideas of aggregate computing.

### Main Ideas

To build spatio-temporal (global) programs in Phyelds, you only need a few simple ideas:

Any function can be marked as part of the aggregate computation with the `@aggregate` decorator, which ensures that the temporal and spatial aspects of the computation are handled correctly.

Specifically, local persistent state is managed with `remember(...)` (similar to what other languages call `rep` or `evolve`), and devices exchange values with neighbors to form `NeighborhoodField`s using `neighbors(...)`.

In the next section, we'll explore these core concepts in more detail with practical examples.

### 1. Local State (`remember`)

Since aggregates follow a self-organizing computational model where nodes repeatedly execute the same program, it is often necessary to maintain some local state across rounds of execution. To do so, Phyelds provides the `remember` primitive, which allows a device to store and update a value that persists across rounds:

```python
from phyelds.calculus import aggregate, remember

@aggregate
def counter():
    # Starts at 0 the first round, then increments each subsequent round
    update_counter, counter_value = remember(0)
    update_counter(counter_value + 1)
    return counter_value
```

`remember(initial_value)` returns a tuple:

1. A function to update the stored value.
2. The current value stored.

In this example, each device maintains a local counter that increments by 1 on each execution round.

### 2. Neighborhood Values (`neighbors`)

Another important aspect of aggregate computing is the ability to interact with neighboring devices. The `neighbors(value)` primitive allows a device to send a value to its neighbors and receive their values in return. This is a kind of bidirectional communication that forms a `NeighborhoodField`:

```python
from phyelds.calculus import aggregate, neighbors

@aggregate
def neighbor_sum():
    # Every device advertises the constant 1; result = number of (neighbors + self)
    nbr = neighbors(1)
    return sum(nbr)
```

Doing so creates a `NeighborhoodField` containing the values received from all neighboring devices (and itself). Calling `sum(nbr)` then computes the total number of devices in the neighborhood (including itself).

With fields, you can perform arithmetic operations directly, as they are overloaded to work element-wise. Therefore, you can, for instance, compute the average temperature in the neighborhood by exchanging temperature readings:

```python
from phyelds.calculus import aggregate, neighbors

@aggregate
def average_temperature(current_temp):
    nbr_temps = neighbors(current_temp)
    return sum(nbr_temps) / sum(neighbors(1))
```

### 3. Combining State + Neighborhood

The previous operators do not really unlock the full potential of aggregate computing. While exchanging values with neighbors is powerful, combining it with local persistent state allows for more complex and adaptive behaviors—in particular, behaviors that emerge over time and space *collectively*.

For instance, we can compute the minimum value seen in the neighborhood over time:

```python
from phyelds.calculus import aggregate, remember, neighbors

@aggregate
def min_over_time(value):
    update_min, local_min = remember(value)
    nbr_mins = neighbors(local_min)
    new_min = min(min(nbr_mins), local_min)
    update_min(new_min)
    return local_min
```

Each device keeps track of the minimum value it has seen so far (`local_min`), exchanges this value with its neighbors (`nbr_mins`), and updates its local minimum if a smaller value is found in the neighborhood. This way, over time, the minimum value propagates through the network of devices.

Therefore, the function `min_over_time(value)` has a global interpretation: it creates a spatio-temporal field where each device eventually converges to the minimum value present in the entire network, despite only having local interactions and state.

This is the essence of aggregate computing: reasoning about global functions without considering the transient local states and interactions of individual devices.

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

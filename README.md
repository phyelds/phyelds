<div align="center">

# Phyelds

Lightweight, pythonic aggregate computing & field calculus toolkit for building, simulating, and experimenting with large scale distributed systems.

[![PyPI version](https://img.shields.io/pypi/v/phyelds.svg)](https://pypi.org/project/phyelds/)
[![Python versions](https://img.shields.io/pypi/pyversions/phyelds.svg)](https://pypi.org/project/phyelds/)
[![License](https://img.shields.io/github/license/phyelds/phyelds.svg)](./LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/phyelds/phyelds.svg)](https://github.com/phyelds/phyelds)
[![Docs](https://img.shields.io/badge/docs-phyelds.github.io-blue.svg)](https://phyelds.github.io/phyelds/)

</div>

---

## Table of Contents

- [Why phyelds?](#why-phyelds)
- [Features](#features)
- [Installation](#installation)
- [Core Concepts](#core-concepts)
  - [Local State (`remember`)](#1-local-state-remember)
  - [Neighborhood Values (`neighbors`)](#2-neighborhood-values-neighbors)
  - [Combining State + Neighborhood](#3-combining-state--neighborhood)
- [Your First Field: the Gradient, Step by Step](#your-first-field-the-gradient-step-by-step)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Running a Minimal Simulation](#running-a-minimal-simulation)
- [Documentation](#documentation)

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

VMAS support is provided by a separate package:

```bash
pip install phyelds-vmas
```

Use the generic simulator from `phyelds.simulator` and VMAS integration from
`phyelds.vmas`:

```python
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, vmas_runner
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

## Your First Field: the Gradient, Step by Step

The *gradient* is the "hello world" of aggregate computing: a field in which every
device holds its distance from the nearest *source* device. It is computed with
nothing but local state and neighbor exchanges, yet it has a global meaning, and it
is the building block of most other patterns: `broadcast`, `collect`, and
`elect_leaders` in `phyelds.libraries` are all built on top of it.

The complete code of this section, including the scripts that produced the
animations, is in [`docs/examples/gradient.py`](docs/examples/gradient.py).

### Step 1 — Each device remembers its estimate

A device cannot know its distance from the source in one shot: it keeps an estimate
and refines it at every round. Local state across rounds is `remember`
(the `rep` of field calculus). Before knowing anything, the estimate is infinity:

```python
set_distance, distance = remember(float("inf"))
```

### Step 2 — Look at the neighbors' estimates

`neighbors(distance)` sends the local estimate to the neighbors and returns a
`NeighborhoodField`: one value per neighbor (plus the device itself). Field
arithmetic is element-wise, so `+ 1` adds one hop to every neighbor's estimate,
giving the distance *through* that neighbor:

```python
through_neighbors = neighbors(distance) + 1
```

### Step 3 — Keep the best one

A source is at distance 0. Any other device takes the shortest path offered by its
neighbors: `exclude_self()` drops the device's own value, so that it cannot
"lean on itself".

```python
from phyelds.calculus import aggregate, neighbors, remember

@aggregate
def hop_gradient(source: bool) -> float:
    set_distance, distance = remember(float("inf"))
    through_neighbors = neighbors(distance) + 1
    nearest = min(through_neighbors.exclude_self().values(), default=float("inf"))
    set_distance(0 if source else nearest)
    return distance
```

Read *locally*, this is a few lines that compare numbers. Read *globally*, it is a
distributed shortest-path algorithm: at every round the correct distances spread
further from the source, until the whole network holds the hop count.

<p align="center">
  <img src="docs/assets/gradient-hops.gif" alt="A hop-count gradient spreading along a line of ten devices" width="640">
</p>

> In the phyelds simulator the devices of one round run one after the other and
> read the freshest messages, so the wave can move more than one hop per round.
> The result does not depend on that order.

### Step 4 — Run it

Every device runs the *same* program. A device reads whether it is a source from
its `source` sensor; the simulator provides the deployment, the neighborhood
relation, and the scheduling:

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all

@aggregate
def program():
    return hop_gradient(sense("source"))

simulator = Simulator()
grid_generation(simulator, width=10, height=1, spacing=1.0)   # a line of 10 devices
simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))
simulator.environment.add_data_for_all_nodes({"source": False})
simulator.environment.nodes[0].data["source"] = True          # device 0 is the source

schedule_program_for_all(simulator, start=0.0, frequency=1.0, program=program)
simulator.run(12)
print([node.data["result"] for node in simulator.environment.nodes.values()])
# [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

To watch it, attach a `RenderMonitor` before `run`. A `.gif` file name is all it
takes to save an animation (an `.mp4` needs ffmpeg):

```python
from phyelds.simulator.effects import DrawEdges, DrawNodes, RenderConfig, RenderMode
from phyelds.simulator.render import RenderMonitor

RenderMonitor(simulator, RenderConfig(
    effects=[DrawEdges(), DrawNodes(color_from="result", cmap="viridis_r", vmin=0, vmax=9)],
    mode=RenderMode.SAVE,
    save_as="gradient.gif",
))
```

### Step 5 — From hops to distances

Hops ignore how far apart devices are. Replacing the constant `1` with the
measured distance to each neighbor gives a metric gradient. That is exactly what
the library `distance_to` does, given `neighbors_distances()`:

```python
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

@aggregate
def program():
    return distance_to(sense("source"), neighbors_distances())
```

<p align="center">
  <img src="docs/assets/gradient-distance.gif" alt="A distance gradient spreading on an irregular lattice from the bottom-left corner" width="480">
</p>

### Step 6 — Self-healing

Nothing in the program refers to *when* the source appeared or where it is: every
round recomputes the field from the current state of the network. So when the
source moves (here, from the bottom-left to the top-right corner, halfway through
the run) the field repairs itself, with no extra code.

<p align="center">
  <img src="docs/assets/gradient-self-healing.gif" alt="The gradient re-converging after the source moves to the opposite corner" width="480">
</p>

Look closely: the area around the new source settles quickly, while the old area
takes longer, because its devices can only raise their stale, too-small estimates
a little at a time, leaning on each other. This is the well-known *rising value
problem* of the classic gradient; the [documentation](https://phyelds.github.io/phyelds/)
covers it among the things to keep in mind when writing aggregate programs.

## Development

```bash
git clone https://github.com/phyelds/phyelds.git
cd phyelds
poetry install
poetry run pytest
poetry run pylint src/
poetry run flake8
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

## Documentation

The full documentation, with the core abstractions, how to integrate phyelds in
other simulators and runtimes, and the pitfalls to avoid, is at
[phyelds.github.io/phyelds](https://phyelds.github.io/phyelds/).

---

Happy field building! ✨

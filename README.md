<div align="center">

<h1><img src="https://raw.githubusercontent.com/phyelds/phyelds/master/docs/assets/phyelds-wordmark.svg" alt="phyelds" width="390"></h1>

Lightweight, pythonic aggregate computing & field calculus toolkit for building, simulating, and experimenting with large scale distributed systems.

[![PyPI version](https://img.shields.io/pypi/v/phyelds.svg)](https://pypi.org/project/phyelds/)
[![Python versions](https://img.shields.io/pypi/pyversions/phyelds.svg)](https://pypi.org/project/phyelds/)
[![Downloads](https://static.pepy.tech/badge/phyelds/month)](https://pepy.tech/project/phyelds)
[![Tests](https://github.com/phyelds/phyelds/actions/workflows/test.yml/badge.svg)](https://github.com/phyelds/phyelds/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/phyelds/phyelds/graph/badge.svg)](https://codecov.io/gh/phyelds/phyelds)
[![Docs](https://github.com/phyelds/phyelds/actions/workflows/docs.yml/badge.svg)](https://phyelds.github.io/phyelds/)
<br>
[![License](https://img.shields.io/github/license/phyelds/phyelds.svg)](https://github.com/phyelds/phyelds/blob/master/LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/phyelds/phyelds.svg)](https://github.com/phyelds/phyelds/commits/master)
[![semantic-release](https://img.shields.io/badge/semantic--release-conventionalcommits-e10079?logo=semantic-release)](https://github.com/semantic-release/semantic-release)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=white)](https://www.conventionalcommits.org/en/v1.0.0/)

**[Documentation](https://phyelds.github.io/phyelds/)** ·
**[Tutorial](https://phyelds.github.io/phyelds/tutorial/)** ·
**[Playground](https://phyelds.github.io/phyelds/playground/)** ·
**[API reference](https://phyelds.github.io/phyelds/reference/calculus/)**

</div>

---

You write **one function** for a whole collective (a swarm of robots, a sensor
network, a fleet of devices) and every device runs it in rounds, exchanging values
only with its neighbors. Global behaviour emerges from local state and local
communication, and the library stays small enough to read in an afternoon.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/phyelds/phyelds/master/docs/assets/channel-dark.gif">
    <img src="https://raw.githubusercontent.com/phyelds/phyelds/master/docs/assets/channel.gif" alt="A self-organizing channel between the bottom-left and top-right corners" width="480">
  </picture>
</p>

## Installation

```bash
pip install phyelds                         # core: the calculus and the libraries
pip install phyelds-simulator               # the simulator, with a compatible phyelds
pip install "phyelds-simulator[jupyter]"    # live rendering inside Jupyter
pip install phyelds-vmas                    # VMAS integration
pip install phyelds-mesa                    # Mesa integration
pip install phyelds-argos                   # ARGoS integration
pip install phyelds-webots                  # Webots integration
```

Requires Python 3.12+.

## A taste

A *channel*: the devices on a route from a source to a target at most `width` longer
than the shortest one. A device is on such a route when its distance from the source
plus its distance from the target is close to the distance between the two, so the
channel is three gradients of the standard library, composed like ordinary Python
functions:

```python
from phyelds.calculus import aggregate
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_between, distance_to

@aggregate
def channel(source: bool, target: bool, width: float) -> bool:
    distances = neighbors_distances()
    to_source = distance_to(source, distances)
    to_target = distance_to(target, distances)
    between = distance_between(source, target, distances)
    return to_source + to_target <= between + width
```

Every device runs the same function, talking only to its neighbors, and the
channel heals by itself when devices move or fail. The
[playground](https://phyelds.github.io/phyelds/playground/#example=channel) runs it
in your browser, and the [tutorial](https://phyelds.github.io/phyelds/tutorial/)
builds the gradient beneath it step by step from `remember` and `neighbors`.

## What's inside

* **Core primitives**: `@aggregate`, `remember`, `neighbors`, `exchange`, `align`, and
  the `NeighborhoodField` abstraction with element-wise arithmetic.
* **Standard libraries**: spreading, collection, gossip, leader election, time &
  reactive state, aggregate processes (`@process` / `spawn`), and spatial/temporal
  logic (SLCS & Past-CTL).
* **Simulator** (`phyelds-simulator`): a pluggable discrete-event simulator with live
  rendering, animation export, and [VMAS](https://github.com/proroklab/VectorizedMultiAgentSimulator)
  integration (`phyelds-vmas`).
* **Mesa** (`phyelds-mesa`): phyelds programs on the agents of a
  [Mesa](https://mesa.readthedocs.io) model.
* **Webots** (`phyelds-webots`): phyelds programs on the robots of a
  [Webots](https://cyberbotics.com) simulation, talking over their simulated radios.
* **ARGoS** (`phyelds-argos`): phyelds programs embedded in native controllers for
  any ARGoS robot, using range-and-bearing radios and compass geometry without GPS.
* **MicroPython**: the same programs run on microcontrollers such as the ESP32
  (`python -m phyelds.micropython`), and talk with devices running CPython.
* **Experimental** (`phyelds.experimental`): studies in progress, whose API will
  probably change, such as collective state machines and swarm behaviours.

Everything is explained in the [documentation](https://phyelds.github.io/phyelds/):
[thinking in fields](https://phyelds.github.io/phyelds/concepts/aggregate-programs/),
[core concepts](https://phyelds.github.io/phyelds/concepts/state/),
[libraries](https://phyelds.github.io/phyelds/concepts/libraries/),
[simulator](https://phyelds.github.io/phyelds/simulator/),
[integration with other runtimes](https://phyelds.github.io/phyelds/integration/),
[MicroPython and the ESP32](https://phyelds.github.io/phyelds/integration/micropython/),
[experimental studies](https://phyelds.github.io/phyelds/experimental/),
and [common pitfalls](https://phyelds.github.io/phyelds/pitfalls/).

## Heritage & Related Projects

**Phyelds** stands on the shoulders of over a decade of research and open-source tools in spatial and aggregate computing, bringing their ideas into a lightweight, Python-native library designed to integrate naturally with Python's scientific, simulation, and machine-learning ecosystem:

* **[Proto](https://proto.bbn.com/)** & **[Protelis](https://protelis.github.io/)** ([GitHub](https://github.com/Protelis/Protelis)) — The pioneering spatial computing and aggregate programming languages that established the computational field abstraction, the `rep` / `nbr` (`remember` / `neighbors`) round-based execution model, and the self-organizing coordination building blocks.
* **[ScaFi](https://scafi.github.io/)** ([GitHub](https://github.com/scafi/scafi)) — The Scala toolkit for aggregate programming, which inspired Phyelds's internal-DSL approach, standard coordination blocks (`G`/`C`/`S`, `summarize`, `channel`, reactive state and time operators), and spatially/temporally scoped aggregate processes (`@process` / `spawn`).
* **[FCPP](https://fcpp.github.io/)** ([GitHub](https://github.com/fcpp/fcpp)) — The high-performance C++ field calculus library, from which Phyelds draws the `exchange` primitive (from Exchange Calculus), resilient coordination strategies (path-coherent gradients, multi-path and point-to-point collection, bounded leader election), and spatial/temporal logic operators (SLCS and Past-CTL).
* **[Collektive](https://github.com/Collektive/collektive)** — The Kotlin Multiplatform aggregate computing DSL, which influenced Phyelds's ergonomic `NeighborhoodField` API and automatic alignment of standard language control flow (`if`/`else` AST rewriting via `@aggregate`).

For the ideas behind the paradigm, see the
[main paper on aggregate computing](https://www.sciencedirect.com/science/article/pii/S235222081930032X).

## Development

```bash
git clone https://github.com/phyelds/phyelds.git
cd phyelds
poetry install
poetry run pytest
poetry run pylint src/
poetry run flake8
```

Contributions are welcome: open an issue for non-trivial changes, keep PRs focused
and tested, and use [Conventional Commits](https://www.conventionalcommits.org/),
since releases are produced from the commit messages.

## Contributors & Acknowledgments

### Main Contributors

* **Gianluca Aguzzi** ([@cric96](https://github.com/cric96)) — [gianluca.aguzzi@unibo.it](mailto:gianluca.aguzzi@unibo.it)
* **Davide Domini** ([@davidedomini](https://github.com/davidedomini)) — [davide.domini@unibo.it](mailto:davide.domini@unibo.it)

### Acknowledgments

Special thanks to **Mirko Viroli**, **Ferruccio Damiani**, **Danilo Pianini**, **Roberto Casadei**, and **Giorgio Audrito** for the insightful discussions, foundational ideas, and continuous feedback that made this project possible.

## License

Apache License 2.0 – see [LICENSE](https://github.com/phyelds/phyelds/blob/master/LICENSE).

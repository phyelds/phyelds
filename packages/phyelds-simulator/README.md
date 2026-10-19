# phyelds-simulator

A discrete-event simulator for [phyelds](https://pypi.org/project/phyelds/) programs,
with live rendering, animation export and data export.

## Installation

```bash
pip install phyelds-simulator                # simulator and a compatible phyelds
pip install "phyelds-simulator[jupyter]"     # live rendering inside Jupyter
```

## Usage

```python
from phyelds.calculus import aggregate, neighbors
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all
```

The import paths are those of phyelds 7, where the simulator was part of `phyelds`.
See the [documentation](https://phyelds.github.io/phyelds/simulator/).

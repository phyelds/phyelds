# phyelds-mesa

[Mesa](https://mesa.readthedocs.io) integration for [phyelds](https://pypi.org/project/phyelds/):
run aggregate programs on the agents of a Mesa model.

## Installation

```bash
pip install phyelds-mesa
```

`phyelds-mesa` installs a compatible `phyelds` release and Mesa.

## Usage

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.mesa import AggregateRuntime, within


@aggregate
def hops_to_source():
    return distance_to(sense("source"), hops_distance())


runtime = AggregateRuntime(
    hops_to_source,
    neighbors=within(1.5),                                 # or cell_neighbors in a grid
    sensors=lambda agent: {"source": agent.unique_id == 1},
)
# In Model.step(): one synchronous round on every agent.
hops = runtime.run_round(model.agents)                     # {unique_id: result}
```

See the [documentation](https://phyelds.github.io/phyelds/integration/mesa/).

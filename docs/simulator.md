# Simulator

`phyelds.simulator` is a small discrete-event simulator for running aggregate
programs on many devices in one process. It is enough for experiments and teaching;
for physics or robotics, see [integration](integration/index.md).

## The pieces

| Piece | Module | Role |
| --- | --- | --- |
| `Simulator` | `phyelds.simulator` | event queue and clock; `run(until)` |
| `Environment`, `Node` | `phyelds.simulator` | the devices: `position`, `data` (sensors and results) |
| deployments | `phyelds.simulator.deployments` | place nodes: `grid_generation`, `deformed_lattice`, `random_in_circle`, `random_walk` |
| neighborhoods | `phyelds.simulator.neighborhood` | who is a neighbor: `radius_neighborhood(r)`, `k_nearest_neighbors(k)`, `full_neighborhood` |
| runner | `phyelds.simulator.runner` | `schedule_program_for_all(simulator, start, frequency, program)` |
| actions | `phyelds.simulator.actions` | recurring movements: `move_with_velocity`, `gaussian_movement` |
| monitors | `phyelds.simulator` / `.render` | observe the run: `Monitor`, `RenderMonitor` |
| exporter | `phyelds.simulator.exporter` | `csv_exporter` writes aggregated outputs to CSV |

## A run, step by step

```python
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import random_in_circle
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all

simulator = Simulator()
random_in_circle(simulator, num_nodes=100, radius=10)
simulator.environment.set_neighborhood_function(radius_neighborhood(2.0))
simulator.environment.add_data_for_all_nodes({"source": False})   # sensors
simulator.environment.nodes[0].data["source"] = True

schedule_program_for_all(simulator, start=0.0, frequency=1.0, program=program)
simulator.run(50)
```

Each node's `data` is both its **sensors** (read with `sense(name)`; `position` and
`time` are added by the runner) and where the runner writes, after each round:

| Key | Content |
| --- | --- |
| `result` | the value returned by the program |
| `outputs` | the values written with `store(name, value)` |
| `messages`, `state` | the runner's bookkeeping: do not edit |

To change a sensor during a run, schedule an event that writes it:

```python
def turn_off_source(node):
    node.data["source"] = False

simulator.schedule_event(25.0, turn_off_source, simulator.environment.nodes[0])
```

!!! warning
    `node.update(new_data=...)` *replaces* the whole `data` dictionary, including
    the program's state. To change one sensor, assign the key.

## Watching a run

`RenderMonitor` draws the network with a list of effects, and either shows it live
(`RenderMode.SHOW`), or saves an animation (`RenderMode.SAVE`) plus a final PNG.
A `.gif` file name is enough to get an animated GIF; `.mp4` needs ffmpeg.

```python
from phyelds.simulator.effects import DrawEdges, DrawNodes, DrawValues, RenderConfig, RenderMode
from phyelds.simulator.render import RenderMonitor

RenderMonitor(simulator, RenderConfig(
    effects=[
        DrawEdges(alpha=0.3),
        DrawNodes(color_from="result", cmap="plasma_r", vmin=0, vmax=20),
        DrawValues(value_from="result", precision=1),
    ],
    dt=1.0,                  # simulated time between two frames
    mode=RenderMode.SAVE,
    save_as="run.gif",
    show_axis=False,
    title="My field",
))
```

| Effect | Draws |
| --- | --- |
| `DrawEdges(alpha)` | the links between neighbors |
| `DrawNodes(color_from, cmap, vmin, vmax, missing_color)` | the nodes; with `cmap`, coloured by the number in `data[color_from]` (missing or infinite values in `missing_color`); without it, `data[color_from]` is used as a colour |
| `DrawValues(value_from, precision, offset)` | the value next to each node (`∞` for infinity) |
| `DrawIDs()` | the node ids |

Fix `vmin` and `vmax` when you animate a field: otherwise the colour scale follows
the values in each frame, and the same colour means different values over time.

A `RenderConfig` is a pydantic model: `config.save(path)` and
`RenderConfig.load(path)` store it as JSON.

## Exporting metrics

`csv_exporter` is an event that, every `time_delta`, aggregates the outputs named in
`metrics` over all nodes (with `mean`, `min` or `max`) and appends a row to
`<output_directory><experiment_name>.csv`. The directory is joined as a string, so
end it with `/`:

```python
from phyelds.simulator.exporter import ExporterConfig, csv_exporter

config = ExporterConfig(
    output_directory="results/",
    experiment_name="gradient",
    metrics=["distance"],             # names written with store(...)
    aggregators=["mean", "max"],
    precision=3,
)
simulator.schedule_event(1.0, csv_exporter, simulator, 1.0, config)
```

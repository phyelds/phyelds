# ARGoS

[ARGoS3](https://github.com/ilpincy/argos3) owns the robots, physics and simulated
radios. `phyelds-argos` runs one aggregate round on each foot-bot per simulation tick.
Each controller owns a [`Device`](micropython.md#the-device-loop): neighbors exchange
its serialized messages over the **range-and-bearing medium**, with delivery on the
next tick. There is no global message table or centrally computed neighborhood.

## Install and build

Use Python **3.12 or 3.13**, a C++17 compiler, CMake 3.18+ and an installed ARGoS3.
The Python development headers and shared library must match the interpreter you use.
UV-managed CPython distributions include both. During development, from the phyelds root:

```bash
pip install -e . -e packages/phyelds-argos
python -m phyelds.argos.build --build-dir build/argos
```

The package ships sources, so the command compiles against your installed ARGoS and
the Python running it. It creates `libphyelds_argos.so` and `libphyelds_argos_qt.so`.
Use `--no-gui` to omit the Qt/OpenGL renderer. With a released package, install
`phyelds-argos` from PyPI first; the same build command applies. Rebuild if you move
or replace the Python environment. ARGoS runs the embedded interpreter selected at
build time, regardless of the `python3` on its launch-time PATH.

## A line of five robots

The complete experiment is in `docs/examples/argos/line.argos`. From the phyelds root:

```bash
PYTHONPATH=docs/examples/argos argos3 -c docs/examples/argos/line.argos
# Without a window:
PYTHONPATH=docs/examples/argos argos3 -z -n -c docs/examples/argos/line.argos
```

The robots stand 0.5 m apart, with a radio range of 0.65 m. They compute distances
`0.00m`, `0.50m`, `1.00m`, `1.50m`, `2.00m` from `fb0`:

```python
--8<-- "argos/gradient.py"
```

Use a `phyelds_controller` in the experiment, with
`library="build/argos/libphyelds_argos"` and
`<params program="gradient:main" source="0" max_speed="0.1" />`.
`program` is an importable `module:function`, not a file to execute. Robot names end
in a unique unsigned 32-bit integer (`fb12` becomes device 12).

## Sensors and outputs

| Sensor | Meaning |
|---|---|
| `time` | Simulation time in seconds |
| `source` | Whether this device ID matches the configured `source`; false if omitted |
| `heading` | Heading unit vector from the compass |
| `obstacle` | Proximity repulsion vector |
| `neighbors_distances` | Map from sender ID to RAB range in metres |
| `neighbors_vectors` | Map from sender ID to its relative vector, in metres |

Vectors are coordinate tuples in the shared compass frame; planar vectors have zero
`z`. The positioning sensor supplies **orientation only**: absolute positions are
never given to programs. `neighbors_distances()` and the experimental
`neighbors_vectors()` automatically use these measured maps. They respect alignment
and remove absent neighbors. Without the maps, their existing position-based
behavior is unchanged; an explicit `position` argument always takes precedence.

| Output through `store` | Meaning |
|---|---|
| `velocity` | Desired global velocity, two or three components, in m/s; capped by `max_speed` (default 0.1) and converted to wheel commands |
| `led` | RGB iterable with three channels in 0–255 |
| `label` | Text above the robot and in the final headless log |

Missing outputs mean a stopped robot, black LEDs and an empty label. Each controller
requires differential steering, LEDs and RAB actuators, plus RAB, positioning and
foot-bot proximity sensors. The line experiment includes the complete configuration.
The optional GUI user function is `phyelds_qtuser_functions`, loaded from
`libphyelds_argos_qt`; it draws a halo and label without changing the simulation.

## Messages and lifecycle

- Frames are `[u32 sender][u16 payload length][Device bytes][zero padding]`, using
  ARGoS `CByteArray` for the header. Use `rab_data_size="4096"` as a starting point;
  the codec's JSON exports are larger than FCPP's binary exports. The host reports an
  error on overflow rather than truncating the message. It does not fragment frames.
- Compact paths are the default. For debugging set `paths="debug"` on **every**
  communicating controller; program versions and path modes must match.
- Each robot has independent aggregate state. A reset clears state, queued messages,
  wheels, LEDs and labels. Missing neighbors are forgotten after one round.
- CPython is initialized once for the process. Worker threads acquire the GIL for
  each round, so ARGoS may use multiple threads but Python rounds run serially.
- Python failures include the traceback, program name and robot ID. `trace="true"`
  logs the label at every round; it is off by default.

The native host does not need FCPP, Boost.Python, pybind11 or phyelds-simulator.
Simulation-specific code stays in this optional package; the core calculus and codec
are reused unchanged. See the companion `phyelds-argos-example` project for metric
gradients, election/counting, dispersion, gathering and flocking with matching FCPP
arenas.

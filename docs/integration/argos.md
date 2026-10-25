# ARGoS

[ARGoS3](https://github.com/ilpincy/argos3) owns the robots, physics and simulated
radios. `phyelds-argos` runs one aggregate round on each robot per simulation tick,
whatever the robot: foot-bot, e-puck, eye-bot, Spiri, Pi-Puck, BuilderBot, drone, block
or prototype. Each controller owns a [`Device`](micropython.md#the-device-loop):
neighbors exchange its serialized messages over the robot's **simulated radio**, with
delivery on the next tick. There is no global message table or centrally computed
neighborhood.

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

## Any robot

The same `phyelds_controller` drives every robot: it uses the devices its experiment
declares, so the configuration of each robot names the devices it has.

| Robot | Radio | Motion | Obstacles | LEDs |
|---|---|---|---|---|
| foot-bot | `range_and_bearing` | `differential_steering` | `footbot_proximity` | `leds` |
| e-puck | `range_and_bearing` | `differential_steering` | `epuck_proximity` | `leds` |
| eye-bot | `range_and_bearing` | `quadrotor_speed` | `eyebot_proximity` | `leds` |
| Spiri | `range_and_bearing` | `quadrotor_speed` | | |
| Pi-Puck | `simple_radios` | `pipuck_differential_drive` | `pipuck_rangefinders` | `pipuck_leds` (on or off) |
| BuilderBot | `simple_radios` | `builderbot_differential_drive` | `builderbot_rangefinders` | `builderbot_leds` |
| drone | `simple_radios` | `drone_flight_system`, actuator and sensor | | `drone_leds` |
| block | `simple_radios` | | | `directional_leds` |
| prototype | `simple_radios` | | | `leds` or `directional_leds` |

Every robot needs a radio, both its actuator and its sensor, and the `positioning`
sensor. The other devices are optional: a robot without them ignores the outputs it
cannot act on, so one program fits a mixed swarm, and robots of different types talk
when they share a medium. Robots from other ARGoS plugins work through the same
generic devices.

The range-and-bearing radio measures where each neighbor is, so programs need no
positions. Simple radios do not: with them, set `gps="true"` in the controller's
`params`, so that programs read their `position` and the geometry helpers compute
distances from shared positions.

## Sensors and outputs

| Sensor | Meaning |
|---|---|
| `time` | Simulation time in seconds |
| `source` | Whether this device ID matches the configured `source`; false if omitted |
| `heading` | Heading unit vector from the compass |
| `obstacle` | Proximity repulsion vector, with a proximity sensor or rangefinders |
| `neighbors_distances` | Map from sender ID to RAB range in metres, with `range_and_bearing` |
| `neighbors_vectors` | Map from sender ID to its relative vector in metres, with `range_and_bearing` |
| `position` | Position in metres, with `gps="true"` |

Vectors are coordinate tuples in the shared compass frame; the vectors to flying
neighbors have a `z`. Unless `gps="true"`, the positioning sensor supplies
**orientation only**: absolute positions are never given to programs.
`neighbors_distances()` and the experimental `neighbors_vectors()` automatically use
the measured maps. They respect alignment and remove absent neighbors. Without the
maps, their existing position-based behavior is unchanged; an explicit `position`
argument always takes precedence.

| Output through `store` | Meaning |
|---|---|
| `velocity` | Desired global velocity, two or three components, in m/s; capped by `max_speed` (default 0.1). Wheeled robots turn towards it, quadrotors and drones fly it |
| `led` | RGB iterable with three channels in 0–255 |
| `label` | Text above the robot and in the final headless log |

Missing outputs mean a stopped robot, black LEDs and an empty label. The line
experiment includes the complete configuration of a foot-bot. The optional GUI user
function is `phyelds_qtuser_functions`, loaded from `libphyelds_argos_qt`; it draws a
halo and label under any robot without changing the simulation.

Some ARGoS models need care:

- **Eye-bot**: `pointmass3d` moves quadrotors by its physics step once per tick, so
  with its default ten iterations the eye-bot flies at a tenth of its speed; give it
  `iterations="1"`.
- **Spiri**: its speed controller oscillates in `pointmass3d`, and diverges with one
  iteration: it flies the right way, but not steadily.
- **Pi-Puck**: under `dynamics3d` it barely turns in place; `dynamics2d` steers it.
- **Drone**: it flies to a target one second ahead, so it stops about a second after
  its velocity does, and it holds its place within a centimetre or so.
- **BuilderBot**: its `obstacle` leaves out the two front rangefinders, which face its
  own end effector.

## Messages and lifecycle

- Frames are `[u32 sender][u16 payload length][Device bytes]`, using ARGoS
  `CByteArray` for the header. On the range-and-bearing radio they are padded with
  zeros to `rab_data_size`: use `rab_data_size="4096"` as a starting point; the codec's
  JSON exports are larger than FCPP's binary exports. The host reports an error on
  overflow rather than truncating the message. It does not fragment frames. Simple
  radios send each frame once on every interface, such as each face of a block.
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

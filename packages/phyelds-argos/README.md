# phyelds-argos

Run [phyelds](https://github.com/phyelds/phyelds) aggregate programs on any ARGoS3 robot:
foot-bot, e-puck, eye-bot, Spiri, Pi-Puck, BuilderBot, drone, block or prototype.
ARGoS owns the robots, physics and radios. Each robot runs a `phyelds.vm.device.Device`;
its bytes travel through the robot's simulated radio, one round per tick.

Install this package into Python 3.12 or 3.13, with ARGoS3, a C++17 compiler and
CMake 3.18+ installed. Build the plugin with the same Python that has your programs:

```bash
python -m phyelds.argos.build --build-dir build
# Without Qt/OpenGL (the controller still drives the LEDs):
python -m phyelds.argos.build --build-dir build-headless --no-gui
```

The package ships C++ sources, not a binary tied to a particular ARGoS/Python ABI.
The command compiles `libphyelds_argos.so` and, unless `--no-gui` is used,
`libphyelds_argos_qt.so`. It uses the calling interpreter and its development
headers/shared library, rather than whichever `python3` happens to be on the PATH.
Rebuild after moving or replacing that Python environment.

In an ARGoS experiment use `phyelds_controller`, with
`library="build/libphyelds_argos"` and `<params program="your_module:your_function"
source="0" max_speed="0.1" />`. Robot names must end in a unique unsigned 32-bit
integer, for example `fb0`, `fb1`. The controller uses the devices the experiment
declares: it needs the `positioning` sensor and a `range_and_bearing` or
`simple_radios` radio (actuator and sensor); motion (`differential_steering`,
`pipuck_differential_drive`, `builderbot_differential_drive`, `quadrotor_speed`,
`drone_flight_system`), proximity sensors and LEDs are optional, and outputs a robot
cannot act on are ignored. Positioning supplies **yaw only**, unless `gps="true"`.

Programs read `time` (seconds), `source` and `heading`; `obstacle` with a proximity
sensor or rangefinders; the `neighbors_distances` and `neighbors_vectors` maps, keyed
by numeric robot ID, with the range-and-bearing radio; and `position` with
`gps="true"`, which simple radios need for geometry. Distances are metres; vectors and
headings share the global compass frame. The standard geometry helpers use the
measured sensors without GPS.

Programs write `velocity` (an iterable with two or three components, m/s), `led`
(three integer RGB channels, 0–255) and `label` (text). `phyelds.argos` names these
sensors and actuators once, as typed objects: `source.sense()`, `led.send((255, 0, 0))`,
`velocity.send(v)`. The maps and `position` are read by the geometry helpers. Missing
outputs mean zero velocity, black LEDs and an empty label. With the GUI enabled,
`<user_functions library="build/libphyelds_argos_qt" label="phyelds_qtuser_functions" />`
draws the LED colour as a halo and the label above each robot.

Radio frames are `[u32 sender][u16 length][Device payload]`, with the header encoded by
ARGoS `CByteArray`, padded with zeros on the range-and-bearing radio. Compact paths are
used by default; `paths="debug"` is available for debugging, but all communicating
robots must use the same mode and program version. Use a sufficiently large
`rab_data_size` (4096 in the examples).
Oversize messages fail explicitly; they are never truncated. Bad frame lengths are
ignored. Payload/codec errors stop the experiment with the robot ID and Python traceback.
`trace="true"` logs each robot's label after every round for diagnostics.

See the [integration guide](https://phyelds.github.io/phyelds/integration/argos/) for
an experiment and the five-example project. The host build needs no Boost.Python,
pybind11, FCPP or phyelds simulator. Python execution is protected by the GIL even
when ARGoS uses worker threads; individual rounds are not executed in parallel.

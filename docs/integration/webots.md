# Webots

[Webots](https://cyberbotics.com) is an open-source robot simulator. The `phyelds-webots`
package runs phyelds programs on its robots: Webots moves the robots and simulates their
radios, and phyelds computes fields on top of them. One controller runs on any robot, and
programs read and write the same sensors and actuators as on [ARGoS](argos.md), so a
program moves between the two unchanged.

```bash
pip install phyelds-webots
```

Install it in the Python that Webots runs the controllers with, which must be Python 3.12
or 3.13. By default Webots runs `python3` from the `PATH`; you can pick another one in the
preferences of Webots, or in the `runtime.ini` of a controller. The `controller` module
comes with Webots.

---

## A line of five robots

Five robots stand in a line, 10 cm apart, and their radio reaches 15 cm. Each robot
measures how far it is from the robot named `source`, over the radio and without a GPS,
and shows it in its label and its LED:

```python
--8<-- "webots/controllers/phyelds_controller/gradient.py:program"
```

The world and the controller are in
[`docs/examples/webots`](https://github.com/phyelds/phyelds/tree/master/docs/examples/webots):
open `worlds/line.wbt` in Webots to run it. The tests run the same world in Webots,
headless. Each robot uses the controller `phyelds_controller`, a file of two lines:

```python
from phyelds.webots import main

if __name__ == "__main__":
    main()
```

and names its program and options in its `controllerArgs`:

```
controller "phyelds_controller"
controllerArgs [ "gradient:main" "--source" "source" ]
```

The program is an importable `module:function`: a module next to the controller, as
`gradient.py` here, or in the Python that runs it.

| Argument | Meaning |
|---|---|
| `--source NAME` | The robot that senses `source`; none if omitted |
| `--emitter NAME`, `--receiver NAME` | The radio, if not the first `Emitter` and `Receiver` of the robot |
| `--gps` | Sense the `position`, from the `GPS` of the robot |
| `--wheel-radius R` | The radius of the wheels, in metres: needed to drive them |
| `--wheels LEFT RIGHT` | The wheel motors, if not `left wheel motor` and `right wheel motor` |
| `--max-speed V` | The top speed of the robot, in m/s (default 0.1) |
| `--on-off-leds` | The LEDs have a colour list: switch them on or off, rather than colour them |
| `--steps-per-round N` | Steps of the world between two rounds (default 1) |
| `--paths compact\|debug` | The path mode of the engine, the same on every robot (default `compact`) |
| `--trace` | Log the label of the robot at every round |

---

## Any robot

The controller uses the devices the robot has, found by their type:

| Device | Use |
|---|---|
| `Emitter` and `Receiver` | The radio, needed: the neighbors of a robot are the robots its `Emitter` reaches |
| `InertialUnit` | The `heading`, the vectors to the neighbors, and steering the wheels |
| `GPS` | The `position`, with `--gps` |
| `DistanceSensor` | The `obstacle`, with an `InertialUnit` |
| `LED` | The `led` output, on every LED |
| `Motor` named `left wheel motor` and `right wheel motor`, or as `--wheels` says | The `velocity` output |

The other devices are optional: a robot without them ignores the outputs it cannot act on,
so one program fits a mixed swarm. Stock robots, such as the e-puck, often have a radio
of infinite range: add an `Emitter` with a `range` and a `Receiver` to their extension
slot, with names of their own, and pass them with `--emitter` and `--receiver`.

These wheeled robots of Webots run under the controller, each with a radio, an
`InertialUnit` and a `GPS` added to the slot of the table:

| Robot | Slot | Arguments | `obstacle` from | LEDs |
|---|---|---|---|---|
| e-puck | `turretSlot` | `--wheel-radius 0.02` | its distance sensors | a colour list: `--on-off-leds` |
| Elisa-3 | `extensionSlot` | `--wheel-radius 0.0045` | its distance sensors | `ledrgb`; its green ones stay off |
| Khepera III | `turretSlot` | `--wheel-radius 0.0212` | its distance sensors | none |
| Khepera IV | `turretSlot` | `--wheel-radius 0.021` | its distance sensors | RGB |
| Thymio II | `bodySlot` | `--wheel-radius 0.021 --wheels motor.left motor.right` | its distance sensors | RGB |
| Create | `bodySlot` | `--wheel-radius 0.031` | none: its sensors look at the floor | a colour list: `--on-off-leds` |
| Pioneer 3-DX | `extensionSlot` | `--wheel-radius 0.0975 --wheels "left wheel" "right wheel"` | its sonars | a colour list: `--on-off-leds` |
| TurtleBot3 Burger | `extensionSlot` | `--wheel-radius 0.033` | none | none |

The tests run each of them in Webots (`packages/phyelds-webots/tests/robots.py`): three
robots in a line measure their distance from the first, one drives along a velocity, and
one in front of a wall senses away from it.

### A mixed swarm

`worlds/mixed.wbt` runs the program of the line on five kinds of robots, 30 cm apart: an
e-puck, the `source`, then an Elisa-3, a Khepera IV, a Thymio II and a TurtleBot3. Only
the arguments of their controllers differ, as the table says. They measure `0.00m`,
`0.31m`, `0.61m`, `0.91m` and `1.22m`: distances are in space, and the radios of the kinds
stand at different heights.

## Sensors and outputs

Programs read the sensors and send the outputs through the typed
[`Sensor` and `Actuator`](../concepts/libraries.md) objects of
`phyelds.libraries.device`, which ARGoS shares:

| Sensor | Meaning |
|---|---|
| `source` | Whether the robot's name is the `--source` one |
| `heading` | Where the robot faces, a horizontal unit vector, with an `InertialUnit` |
| `obstacle` | Away from what the distance sensors see, in the frame of the world; `None` without them or an `InertialUnit` |

The host also gives the time and the geometry of the neighbors; the libraries of phyelds
read them:

| Host sensor | Meaning | Read by |
|---|---|---|
| `time` | The simulation time, in seconds | `local_time()` |
| `neighbors_distances` | Map from neighbor name to distance in metres | `neighbors_distances()` |
| `neighbors_vectors` | Map from neighbor name to its vector, in the frame of the world, with an `InertialUnit` | `neighbors_vectors()` |
| `position` | Position in metres, with `--gps` | `local_position()` |

The `Receiver` measures where each message comes from: Webots gives its signal strength,
1/r², and the direction of its emitter. Its `signalStrengthNoise` and `directionNoise`
fields make them noisy. The `InertialUnit` must be aligned with the `Receiver`.

Each distance sensor pushes away from where it looks, as its pose in the URDF of the robot
(`Robot.getUrdf()`) gives it, by how close it sees something: 1 touching and 0 at the end
of its range, in distance, through its lookup table. Infra-red sensors see the colour of
what they look at: they miss dark objects.

| Actuator | Meaning |
|---|---|
| `velocity` | Desired velocity in the frame of the world, in m/s, capped by `--max-speed`: the robot turns towards it and drives as it faces it |
| `led` | RGB iterable with three channels in 0–255: the colour of an RGB LED (`gradual TRUE`, empty `color`), or on and off with `--on-off-leds` |
| `label` | Text logged with `--trace`, and when the world ends |

Missing outputs mean a still robot and dark LEDs. Webots does not tell a controller which
kind an LED is, so a robot with both kinds needs a controller of its own.

---

## A controller of your own

`phyelds.webots.AggregateController` runs the rounds of a robot on
[`phyelds.vm.device.Device`](micropython.md#the-device-loop), for a controller that drives
its robot itself; `phyelds.webots.Body` applies the outputs as `main()` does:

```python
from controller import Robot

from phyelds.webots import AggregateController, Body

robot = Robot()
body = Body(robot, wheel_radius=0.02)
aggregate_controller = AggregateController(
    robot, program, inertial_unit="inertial unit", sensors=body.sense
)
while robot.step(int(robot.getBasicTimeStep())) != -1:
    aggregate_controller.run_round()
    body.act(aggregate_controller.outputs)
```

- **Devices**: each robot is a device, identified by its name. **Robot names must be
  unique.**
- **Rounds**: `run_round()` runs the program once, and returns its result. Call it after
  each `robot.step`.
- **Synchronous rounds**: Webots delivers a message in the step after it was sent. With a
  round at every step of every robot, a robot receives in each round what its neighbors
  sent in the previous one, as in the phyelds simulator. A neighbor that stops sending is
  forgotten at the next round.
- **Sensors**: `gps=` and `inertial_unit=` name the devices to sense with; `sensors=` adds
  more, from a function called at each round.

---

## Notes

- **Messages are bytes**: they are encoded with [the wire
  format](micropython.md#the-wire-format), so what travels must be something the codec
  knows. Values of your own dataclasses need `register`.
- **Compact paths**: they make the messages smaller (see [compact
  paths](micropython.md#compact-paths)). All the robots must use the same mode.
- **Speed**: a round at every step is slow with many robots, each a Python process: 32
  robots ran at 0.3x real time with a round every 32 ms step, and at about 8x with
  `--steps-per-round 4`.
- **Headless runs**: `webots --batch --mode=fast --no-rendering --minimize --stdout
  --stderr world.wbt` runs a world without a window, for instance in CI under `xvfb-run`.

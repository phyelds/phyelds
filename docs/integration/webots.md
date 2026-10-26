# Webots

[Webots](https://cyberbotics.com) is an open-source robot simulator. The `phyelds-webots`
package runs phyelds programs on its robots: Webots moves the robots and simulates their
radios, and phyelds computes fields on top of them.

```bash
pip install phyelds-webots
```

Install it in the Python that Webots runs the controllers with, which must be Python 3.12
or later. By default Webots runs `python3` from the `PATH`; you can pick another one in the
preferences of Webots, or in the `runtime.ini` of a controller. The `controller` module
comes with Webots.

---

## How it works

In Webots each robot runs its own controller, in its own process: nobody sees the whole
swarm. So each robot is a device that talks over a radio, as a board does (see
[MicroPython and the ESP32](micropython.md)). `phyelds.webots.AggregateController` runs the
rounds of a robot on [`phyelds.vm.device.Device`](micropython.md#the-device-loop):

- **Devices**: each robot is a device, identified by its name. **Robot names must be
  unique.**
- **Rounds**: `run_round()` runs the program once, and returns its result. Call it after
  each `robot.step`.
- **Neighbors**: the robots whose `Receiver` the `Emitter` of the robot reaches. Its
  `range` field sets the communication range; an `infra-red` emitter also needs a line of
  sight.
- **Synchronous rounds**: Webots delivers a message in the step after it was sent. With a
  round at every step of every robot, a robot receives in each round what its neighbors
  sent in the previous one, as in the phyelds simulator. A neighbor that stops sending is
  forgotten at the next round.
- **Sensors**: every robot senses `time` (the simulation time) and, if you pass the name
  of a `GPS` device with `gps=`, its `position`. `sensors=` adds more, from a function
  called at each round.
- **Distances**: the `Receiver` measures how far each message comes from, so
  `neighbors_distances()` gives the distance to each neighbor, in metres, without a
  `GPS`. Its `signalStrengthNoise` field makes the measure noisy. With the name of an
  `InertialUnit` (`inertial_unit=`), aligned with the `Receiver`, `neighbors_vectors()`
  gives the vector to each neighbor too, in the frame of the world, and the robot senses
  its `heading`, a horizontal unit vector.
- **Outputs**: what the program `store`s is in `outputs`; the controller applies it to the
  robot (motors, LEDs).

The robot needs an `Emitter` and a `Receiver`, by default named `emitter` and `receiver`
(`emitter=` and `receiver=` choose others).

---

## Example

Five robots stand in a line, 10 cm apart, and their radio reaches 15 cm. Each robot
computes how many hops it is from the robot named `source`, and lights its LED when it is
close to it:

```python
--8<-- "webots/controllers/phyelds_gradient/phyelds_gradient.py:controller"
```

The world and the controller are in
[`docs/examples/webots`](https://github.com/phyelds/phyelds/tree/master/docs/examples/webots):
open `worlds/line.wbt` in Webots to run it. The tests run the same world in Webots,
headless.

---

## Notes

- **Messages are bytes**: they are encoded with [the wire
  format](micropython.md#the-wire-format), so what travels must be something the codec
  knows. Values of your own dataclasses need `register`.
- **Compact paths**: `paths="compact"` makes the messages smaller (see [compact
  paths](micropython.md#compact-paths)). All the robots must use the same mode.
- **Headless runs**: `webots --batch --mode=fast --no-rendering --minimize --stdout
  --stderr world.wbt` runs a world without a window, for instance in CI under `xvfb-run`.

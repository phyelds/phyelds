# phyelds-webots

[Webots](https://cyberbotics.com) integration for [phyelds](https://pypi.org/project/phyelds/):
run aggregate programs on the robots of a Webots simulation. One controller runs on any
robot, and programs read and write the same sensors and actuators as on ARGoS.

## Installation

Install it in the Python that Webots runs the controllers with (Python 3.12 or 3.13):

```bash
pip install phyelds-webots
```

The `controller` module comes with Webots.

## Usage

Give each robot an `Emitter` and a `Receiver`: the range of the emitter decides who the
neighbors are, and the receiver measures how far they are. Write the program:

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import label, source
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to


@aggregate
def main():
    distance = distance_to(source.sense(), neighbors_distances())   # metres, without GPS
    return label.send(f"{distance:.2f}m")
```

The controller of every robot is `controllers/phyelds_controller/phyelds_controller.py`:

```python
from phyelds.webots import main

if __name__ == "__main__":
    main()
```

and the world names the program, next to the controller, and its options:

```
controller "phyelds_controller"
controllerArgs [ "gradient:main" "--source" "source" ]
```

With an `InertialUnit` the robot also senses its `heading` and the vectors to its
neighbors; `--gps` adds its `position`. The `led` output colours its LEDs, and the
`velocity` output drives its wheels, given `--wheel-radius`. `AggregateController` and
`Body` are there for a controller of your own.

See the [documentation](https://phyelds.github.io/phyelds/integration/webots/).

# phyelds-webots

[Webots](https://cyberbotics.com) integration for [phyelds](https://pypi.org/project/phyelds/):
run aggregate programs on the robots of a Webots simulation.

## Installation

Install it in the Python that Webots runs the controllers with (Python 3.12 or later):

```bash
pip install phyelds-webots
```

The `controller` module comes with Webots.

## Usage

Give each robot an `Emitter`, a `Receiver` and, for the `position` sensor, a `GPS`; the range
of the emitter decides who the neighbors are. Then, in the controller:

```python
from controller import Robot

from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.webots import AggregateController


@aggregate
def hops_to_source():
    return distance_to(sense("source"), hops_distance())


robot = Robot()
aggregate_controller = AggregateController(
    robot, hops_to_source, gps="gps", sensors=lambda: {"source": robot.getName() == "source"}
)
while robot.step(int(robot.getBasicTimeStep())) != -1:
    hops = aggregate_controller.run_round()   # one round per step
```

See the [documentation](https://phyelds.github.io/phyelds/integration/webots/).

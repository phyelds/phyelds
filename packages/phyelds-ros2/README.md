# phyelds-ros2

[ROS 2](https://docs.ros.org) integration for [phyelds](https://pypi.org/project/phyelds/):
run aggregate programs on ROS 2 robots, real or simulated, one node per robot.

## Installation

Install it in the Python of your ROS 2 distribution, Jazzy or later (Python 3.12 or newer):

```bash
pip install phyelds-ros2
```

`rclpy` and the messages come with ROS 2.

## Usage

Each robot runs a node in its own namespace, which names the robot:

```bash
python -m phyelds.ros2 turtles:main --sense turtlesim --neighbourhood range --range 3.5 \
    --source turtle1 --ros-args -r __ns:=/turtle2
```

The node turns the topics of its robot into sensors and the outputs of its program into
messages, through `SensorTopic`s and `ActuatorTopic`s: odometry, turtlesim poses,
differential and holonomic `cmd_vel` drives and text are ready, `reading` and `command` wire
one field of any topic, and `--topics module:function` adds those of your own. The nodes
talk to each other on `/phyelds/messages`. A neighbourhood strategy decides which senders
are neighbours:

- `Reachable()`: whoever the network delivers; with `measure=True`, each message carries
  the position of its sender, and neighbours come with their distance and vector;
- `WithinRange(radius)`: the senders within `radius` metres, from those positions.

`AggregateRosNode` is the node for a launcher in Python, and `AggregateNode` the rounds
without ROS.

See the [documentation](https://phyelds.github.io/phyelds/integration/ros2/).

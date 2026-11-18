# ROS 2

[ROS 2](https://docs.ros.org) is the middleware of most robots, real and simulated. The
`phyelds-ros2` package runs a phyelds program on each robot as a ROS 2 node: the node turns
the topics of its robot into sensors and its outputs into messages, and talks to the other
nodes over one shared topic. Which topics, and how, is up to the robot: odometry and a
`cmd_vel` twist are ready, and any other topic takes a line. The program uses the same
sensors and actuators as on [Webots](webots.md) and [ARGoS](argos.md).

```bash
pip install phyelds-ros2
```

Install it in the Python of your ROS 2 distribution, which must be Python 3.12 or newer:
ROS 2 Jazzy or later. Humble ships Python 3.10, which phyelds does not support. `rclpy` and
the messages come with ROS 2.

---

## Five turtles

Five turtles of [turtlesim](https://docs.ros.org/en/jazzy/Tutorials/Beginner-CLI-Tools/Introducing-Turtlesim/Introducing-Turtlesim.html)
hear each other within 3.5 m. Each measures how far `turtle1` is, along the network, shows it
in its label, and heads to it until it is 1.5 m away:

```python
--8<-- "ros2/turtles.py:program"
```

`turtle5` starts out of the range of `turtle1`: it measures its distance through `turtle2` or
`turtle4`, and follows them.

```python
--8<-- "ros2/turtles.launch.py:turtles"
```

The program and the launch file are in
[`docs/examples/ros2`](https://github.com/phyelds/phyelds/tree/master/docs/examples/ros2).
Run it from that directory, so that the nodes import `turtles`:

```bash
sudo apt install ros-jazzy-turtlesim
source /opt/ros/jazzy/setup.bash
cd docs/examples/ros2
ros2 launch turtles.launch.py
ros2 topic echo /turtle5/label   # in another terminal
```

Each turtle has its node, started as:

```bash
python -m phyelds.ros2 turtles:main --sense turtlesim --neighbourhood range --range 3.5 \
    --source turtle1 --max-speed 1.0 --ros-args -r __ns:=/turtle2
```

The program is an importable `module:function`. The node lives in the namespace of its
robot, whose name, without slashes, is the id of the robot: **namespaces must be unique**.

| Argument | Meaning |
|---|---|
| `--id ID` | The id of the robot, if not its namespace |
| `--source ID` | The robot that senses `source`; none if omitted |
| `--neighbourhood reachable\|range` | Who is a neighbour (default `reachable`): see [neighbourhoods](#neighbourhoods) |
| `--range R` | With `range`, how far a robot reaches, in metres |
| `--measure` | With `reachable`, measure the neighbours from their positions |
| `--sense [odom] [turtlesim] [scan]` | The topics to sense, see [any robot](#any-robot) (default `odom`; none if empty) |
| `--act [differential] [holonomic] [label]` | The outputs to act on (default `differential label`; none if empty) |
| `--topics module:function` | A function that returns more topics, of your own |
| `--period T` | The time between two rounds, in seconds (default 0.1) |
| `--max-speed V` | The top speed of the robot, in m/s (default 0.2) |
| `--turn-rate K` | How fast it turns, in rad/s for each radian it is off its velocity (default 1) |
| `--topic NAME` | The topic all the nodes share (default `/phyelds/messages`) |
| `--lifetime N` | For how many rounds the message of a silent neighbour is kept (default 2) |

The ROS arguments follow `--ros-args`, as for any node: `-p use_sim_time:=true` makes the
rounds follow the clock of a simulator.

---

## Any robot

Robots differ in their topics, so the node takes them as a list. A `SensorTopic` turns each
message of a topic into sensors, which hold until the next message; an `ActuatorTopic` turns
an output of the program into a message, after each round. Topics are relative to the
namespace of the robot, and `-r` remaps them. These are ready, in `phyelds.ros2.topics`:

| Topic | Option | Type | Use |
|---|---|---|---|
| `odometry("odom")` | `--sense odom` | `nav_msgs/Odometry` | The `position` and `heading` of the robot |
| `turtle_pose("pose")` | `--sense turtlesim` | `turtlesim/Pose` | The `position` and `heading` of a turtle |
| `laser_obstacle("scan")` | `--sense scan` | `sensor_msgs/LaserScan` | The `obstacle`: away from the nearest thing the scan sees, in the frame of the world, 1 at `range_min` and 0 at `range_max`; it needs the `heading` |
| `differential_drive("cmd_vel")` | `--act differential` | `geometry_msgs/Twist` | The `velocity`, for a robot that turns to move: it turns towards it, and drives forward as it faces it |
| `holonomic_drive("cmd_vel")` | `--act holonomic` | `geometry_msgs/Twist` | The `velocity`, for a robot that moves in any direction: `linear.x` and `linear.y`, in its frame |
| `text("label")` | `--act label` | `std_msgs/String` | The `label` output, as text |
| `reading(name, topic, type, field="data")` | | any | One field of the messages, as the sensor `name` |
| `command(output, topic, type, field="data")` | | any | An output, as it is, in one field of the messages |

The drives need the `heading`, from a sensor topic, and send nothing before it. A round that
does not send an output publishes nothing on its topic, so that another controller can drive
the robot meanwhile.

The rest of a robot takes a function that returns its topics, given with `--topics`:

```python
from phyelds.ros2.topics import SensorTopic, command, reading

def robot():
    return [
        reading("battery", "battery_state", "sensor_msgs/msg/BatteryState", field="percentage"),
        command("grip", "gripper", "std_msgs/msg/Bool"),
        SensorTopic("scan", "sensor_msgs/msg/LaserScan",
                    lambda scan, sensors: {"nearest": min(scan.ranges)}),
    ]
```

```bash
python -m phyelds.ros2 program:main --topics my_robot:robot --ros-args -r __ns:=/robot1
```

Types are named as ROS names them, `package/msg/Type`. The conversions see only the fields
of the messages, so they are tested without ROS. A `SensorTopic` of your own takes
`read(message, sensors)`: it returns the sensors a message gives, from the message and the
latest sensors, such as the `heading` to turn a reading into the frame of the world. An
`ActuatorTopic` of your own takes
`write(message, value, sensors)`: it fills a new message from the value of the output and
the latest sensors, and returns whether to publish it.

All the nodes also share `/phyelds/messages`, a `std_msgs/UInt8MultiArray` topic, best
effort. Each message is a line of JSON, with the id of its sender and what the
neighbourhood needs, followed by the bytes of its [`Device`](micropython.md#the-device-loop).

---

## Neighbourhoods

Every node hears the shared topic, and a strategy decides which senders are neighbours.

- **`Reachable()`**, the default: the network decides. Every node heard is a neighbour. On
  one host, a LAN or in a simulator, every node hears every other. On robots that talk over
  an ad-hoc or mesh radio, the nodes heard are those in range. With `measure=True`
  (`--measure`), each message carries the position of its sender, and neighbours come with
  their distance and vector; they are admitted however far they are.
- **`WithinRange(radius)`** (`--neighbourhood range --range R`): the senders within `radius`
  metres, from the positions in their messages. It brings the range of a radio to a
  simulator, where the network has none.

A sender whose position is not known yet is a neighbour of `Reachable` without a distance,
and is not a neighbour of `WithinRange`. Positions must be in a frame all the robots share:
that of turtlesim, of the world of a simulator, or `map`. The `odom` of a real robot starts
where the robot starts, so it needs a shared localisation first.

A strategy of your own implements `Neighbourhood`: `header(position)` returns what to add to
the messages of a node, `admit(header, position)` returns a `Neighbour`, with its `distance`
and `vector` if known, or `None` for a sender that is not a neighbour, and `measures` says
whether it measures its neighbours.

---

## Sensors and outputs

| Sensor | Meaning | Read by |
|---|---|---|
| `source` | Whether the id of the robot is the `--source` one | `source.sense()` |
| `time` | The time of the node, in seconds: the simulation time with `use_sim_time` | `local_time()` |
| `position` | The position, from a sensor topic; `None` until sensed | `local_position()` |
| `heading` | Where the robot faces, a horizontal unit vector, from a sensor topic | `heading.sense()` |
| `obstacle` | Away from the nearest thing a laser scan sees, in the frame of the world, with `laser_obstacle` | `obstacle.sense()` |
| any other | What the sensor topics give | `sense(name)` |
| `neighbors_distances` | Map from neighbour id to distance, when the neighbourhood measures them | `neighbors_distances()` |
| `neighbors_vectors` | Map from neighbour id to its vector, in the frame of the positions | `neighbors_vectors()` |

When the neighbourhood measures, the node always gives `neighbors_distances` and
`neighbors_vectors`, empty before any neighbour is measured. When it does not, the node gives
neither, and `neighbors_distances()` shares positions instead.

| Actuator | Meaning |
|---|---|
| `velocity` | Desired velocity in the frame of the positions, in m/s, capped by `--max-speed`, for a drive |
| `label` | Text, for `text()` |
| any other | For an actuator topic of your own |

---

## A node of your own

`phyelds.ros2.AggregateRosNode` is the node `main()` runs, for a launcher in Python: it takes
the program, the `neighbourhood`, the `sensor_topics` and `actuator_topics`, and `sensors=`
of your own; its `node` is an `rclpy` node to spin. `phyelds.ros2.AggregateNode` holds the
rounds without ROS: give it what the robot hears (`hear`) and senses (`sense`), call
`run_round(time)` and publish the bytes it returns, then act on its `outputs`.

- **Asynchronous rounds**: each node runs its rounds on its own timer, so the rounds of
  neighbours are not aligned (see the [rounds of each host](index.md#rounds-of-each-host)).
  A neighbour may send twice, or not at all, between two rounds: its message is kept for
  `--lifetime` rounds, 2 by default.
- **Messages are bytes**, encoded with [the wire format](micropython.md#the-wire-format), in
  [compact paths](micropython.md#compact-paths): all the nodes must use the same mode.

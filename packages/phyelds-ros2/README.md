# phyelds-ros2

[ROS 2](https://docs.ros.org) integration for [phyelds](https://pypi.org/project/phyelds/):
run aggregate programs on ROS 2 robots, one node per robot. Work in progress
([#100](https://github.com/phyelds/phyelds/issues/100)): not yet released.

Each node runs a device, whose messages travel as bytes on a topic all the nodes share. A
neighbourhood strategy decides which senders are its neighbours:

- `Reachable()`: whoever the network delivers; with `measure=True`, each message carries
  the position of its sender, and neighbours come with their distance and vector;
- `WithinRange(radius)`: the senders within `radius` metres, from those positions.

It targets ROS 2 Jazzy or later, whose Python is 3.12 or newer.

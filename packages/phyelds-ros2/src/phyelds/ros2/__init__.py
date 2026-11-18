"""
Run phyelds programs on ROS 2 robots, one node per robot.

Each node is a device: its messages travel as bytes on a topic that all the nodes share, and
a neighbourhood strategy decides which senders are its neighbours.
"""

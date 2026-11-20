import uuid

import pytest

from phyelds.calculus import aggregate
from phyelds.libraries.device import label, sense, store, velocity
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.ros2 import AggregateRosNode, Transforms, WithinRange
from phyelds.ros2.host import tf_locator
from phyelds.ros2.topics import command, reading

rclpy = pytest.importorskip("rclpy")

# pylint: disable=wrong-import-position,wrong-import-order,import-error
from geometry_msgs.msg import Twist  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from std_msgs.msg import Bool, Float32, String  # noqa: E402

ROUNDS = 30
SPINS = 20_000


@aggregate
def metres_to_source():
    distance = float(distance_to(sense("source"), neighbors_distances()))
    label.send(f"{distance:.1f}")
    velocity.send((0.0, 1.0))
    return distance


@pytest.fixture(name="executor")
def _executor():
    rclpy.init()
    executor = SingleThreadedExecutor()
    yield executor
    executor.shutdown()
    rclpy.try_shutdown()


def _robots(executor, xs):
    topic = f"/phyelds/test_{uuid.uuid4().hex}"
    hosts = [
        AggregateRosNode(
            metres_to_source, namespace=f"/r{index}", neighbourhood=WithinRange(1.6), period=0.02,
            topic=topic, sensors=lambda index=index: {"source": index == 0},
        )
        for index in range(len(xs))
    ]
    odometry = rclpy.create_node("odometry")
    publishers = [odometry.create_publisher(Odometry, f"/r{index}/odom", 10) for index in range(len(xs))]

    def publish():
        for publisher, x in zip(publishers, xs):
            message = Odometry()
            message.pose.pose.position.x = x
            message.pose.pose.orientation.w = 1.0
            publisher.publish(message)

    odometry.create_timer(0.01, publish)
    for node in [odometry, *(host.node for host in hosts)]:
        executor.add_node(node)
    return hosts, odometry


def _spin(executor, hosts, rounds=ROUNDS):
    for _ in range(SPINS):
        if min(host.rounds for host in hosts) >= rounds:
            return
        executor.spin_once(timeout_sec=0.01)
    pytest.fail("the nodes did not run their rounds")


def test_nodes_compute_a_gradient_over_the_shared_topic(executor):
    hosts, _ = _robots(executor, [0.0, 1.0, 2.5])

    _spin(executor, hosts)

    assert [host.aggregate.device_id for host in hosts] == ["r0", "r1", "r2"]
    assert [host.aggregate.result for host in hosts] == pytest.approx([0.0, 1.0, 2.5])


def test_nodes_publish_the_twist_and_the_label_of_their_program(executor):
    hosts, odometry = _robots(executor, [0.0, 1.0])
    twists, labels = [], []
    odometry.create_subscription(Twist, "/r1/cmd_vel", twists.append, 10)
    odometry.create_subscription(String, "/r1/label", labels.append, 10)

    _spin(executor, hosts)

    assert twists and twists[-1].linear.x == pytest.approx(0.0, abs=1e-9) and twists[-1].angular.z > 0.0
    assert labels and labels[-1].data == "1.0"


@aggregate
def battery_alarm():
    store("alarm", sense("battery") is not None and sense("battery") < 0.2)


def test_nodes_sense_and_act_on_topics_of_ones_own(executor):
    topic = f"/phyelds/test_{uuid.uuid4().hex}"
    host = AggregateRosNode(
        battery_alarm, namespace="/r0", period=0.02, topic=topic,
        sensor_topics=[reading("battery", "battery", "std_msgs/msg/Float32")],
        actuator_topics=[command("alarm", "alarm", "std_msgs/msg/Bool")],
    )
    battery = rclpy.create_node("battery")
    publisher = battery.create_publisher(Float32, "/r0/battery", 10)
    battery.create_timer(0.01, lambda: publisher.publish(Float32(data=0.1)))
    alarms = []
    battery.create_subscription(Bool, "/r0/alarm", alarms.append, 10)
    executor.add_node(host.node)
    executor.add_node(battery)

    _spin(executor, [host])

    assert alarms and alarms[-1].data is True


def test_nodes_measure_their_neighbours_from_tf2_transforms(executor):
    # pylint: disable=import-outside-toplevel
    from geometry_msgs.msg import TransformStamped
    from tf2_ros import StaticTransformBroadcaster

    topic = f"/phyelds/test_{uuid.uuid4().hex}"
    xs = [0.0, 1.0, 2.5]
    hosts = [
        AggregateRosNode(
            metres_to_source, namespace=f"/r{index}", period=0.02, topic=topic, sensor_topics=[],
            neighbourhood=lambda node: Transforms(f"{node.get_namespace().strip('/')}/base_link",
                                                  tf_locator(node, "map"), radius=1.6),
            sensors=lambda index=index: {"source": index == 0},
        )
        for index in range(len(xs))
    ]
    frames = rclpy.create_node("frames")
    broadcaster = StaticTransformBroadcaster(frames)
    transforms = []
    for index, x in enumerate(xs):
        transform = TransformStamped()
        transform.header.frame_id, transform.child_frame_id = "map", f"r{index}/base_link"
        transform.transform.translation.x = x
        transform.transform.rotation.w = 1.0
        transforms.append(transform)
    broadcaster.sendTransform(transforms)
    for node in [frames, *(host.node for host in hosts)]:
        executor.add_node(node)

    _spin(executor, hosts)

    assert [host.aggregate.result for host in hosts] == pytest.approx([0.0, 1.0, 2.5])

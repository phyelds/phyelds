"""
Each robot computes how many radio hops it is from the robot named ``source``, lights its
LED when it is close, and prints its distance whenever it changes.

Open ``docs/examples/webots/worlds/line.wbt`` in Webots, with phyelds-webots installed in
the Python that runs the controllers.
"""
from controller import Robot  # pylint: disable=import-error

from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.webots import AggregateController


# --8<-- [start:controller]
@aggregate
def hops_to_source():
    """Hops to the source; the LED shows the area around it."""
    distance = distance_to(sense("source"), hops_distance())
    store("led", distance < 2)
    return distance


def main() -> None:
    """Run a round at every step, and apply the outputs to the robot."""
    robot = Robot()
    is_source = robot.getName() == "source"
    aggregate_controller = AggregateController(
        robot, hops_to_source, sensors=lambda: {"source": is_source}
    )
    led = robot.getDevice("led")
    last = None
    while robot.step(int(robot.getBasicTimeStep())) != -1:
        hops = aggregate_controller.run_round()
        led.set(int(aggregate_controller.outputs["led"]))
        if hops != last:
            print("phyelds", robot.getName(), hops, flush=True)
            last = hops
# --8<-- [end:controller]


if __name__ == "__main__":
    main()

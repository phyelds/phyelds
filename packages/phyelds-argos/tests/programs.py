"""Small programs loaded by the native integration tests."""
import math
import json
from phyelds.argos import heading, label, led, obstacle, source, time, velocity
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.device import local_id
from phyelds.libraries.time import counter
from phyelds.experimental.swarm import neighbors_vectors


@aggregate
def gradient() -> float:
    """A metric gradient with no position sensor."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(str(round(distance * 2)) if math.isfinite(distance) else "?")
    return distance


@aggregate
def metric_gradient() -> None:
    """The distance from the source in metres, lit blue on the source and red elsewhere."""
    distance = float(distance_to(source.sense(), neighbors_distances()))
    label.send(f"{distance:.3f}")
    led.send((0, 0, 255) if source.sense() else (255, 0, 0))


@aggregate
def probe() -> None:
    """Report only locally available state, including the absence of GPS."""
    label.send(json.dumps({
        "id": local_id(), "round": int(counter()), "time": time.sense(), "heading": heading.sense(),
        "position": sense("position"),
        "ranges": neighbors_distances().data,
        "vectors": {node_id: tuple(value) for node_id, value in neighbors_vectors().data.items()},
    }))


def drive() -> None:
    """Head along the global x axis at 5 cm/s, and report where the robot is."""
    velocity.send((0.05, 0))
    label.send(json.dumps(sense("position")))


def avoid() -> None:
    """Report the repulsion of the obstacles the robot senses, if it can."""
    label.send(json.dumps(obstacle.sense()))


def broken() -> None:
    """Fail inside Python so the original traceback must cross the native host."""
    raise ValueError("deliberate program error")


# The programs below write with store, which checks nothing: the host checks every output.


def bad_velocity() -> None:
    """An invalid actuator output must not reach the physics engine."""
    store("velocity", (float("nan"), 0))


def bad_led() -> None:
    """An invalid colour must not wrap to a different UInt8 value."""
    store("led", (256, 0, 0))


def bad_label() -> None:
    """An unencodable Python string must report its error, never crash C++."""
    store("label", chr(0xD800))

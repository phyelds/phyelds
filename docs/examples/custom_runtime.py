"""
Running phyelds programs outside the bundled simulator.

phyelds only needs, for each device and each round:

1. a ``NodeContext`` with the device id and its sensors;
2. the messages the neighbors sent in their last round;
3. the state the device kept from its previous round.

It gives back the messages to send, the state to keep, and the outputs (actuations)
the program stored. This file drives that loop with plain Python objects; a real
runtime (a robot, a game engine, a network simulator) does the same with its own
transport and storage.

    poetry run python docs/examples/custom_runtime.py
"""
import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from phyelds import engine
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.data import State
from phyelds.libraries.device import sense, store
from phyelds.vm import NodeContext
from phyelds.vm.internal import MutableEngine

INFINITY = float("inf")


@dataclass
class Device:
    """What a runtime keeps for each device between two rounds."""
    device_id: int
    sensors: dict[str, Any]
    state: dict[str, Any] = field(default_factory=dict)
    outbox: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)


# --8<-- [start:run_round]
def run_round(device: Device, inbox: dict[int, dict[str, Any]], program: Callable) -> Any:
    """
    Run one round of ``program`` on ``device``.

    Args:
        device: the device, updated in place with its new state, outbox and outputs.
        inbox: the last outbox of each neighbor, by neighbor id.
        program: an ``@aggregate`` function.

    Returns:
        The value computed by the program in this round.
    """
    engine.set(MutableEngine())
    engine.get().setup(NodeContext(device.device_id, device.sensors), inbox, device.state)
    result = program()
    device.outbox = engine.get().cooldown()  # first: it also drops the state not used
    device.state = engine.get().state_trace()
    device.outputs = engine.get().node_context.outputs
    return result.value if isinstance(result, State) else result
# --8<-- [end:run_round]


def collect_inbox(
    devices: dict[int, Device], links: dict[int, list[int]], device_id: int
) -> dict[int, dict[str, Any]]:
    """
    The messages a device receives: a copy of each neighbor's last outbox, as a real
    network would deliver them (sharing the objects would let devices mutate each other).
    """
    return {
        neighbor: copy.deepcopy(devices[neighbor].outbox) for neighbor in links[device_id]
    }


def run_rounds(
    devices: dict[int, Device], links: dict[int, list[int]], program: Callable, rounds: int
) -> dict[int, Any]:
    """Run ``rounds`` rounds on every device, in id order; return the last results."""
    results = {}
    for _ in range(rounds):
        for device_id, device in devices.items():
            inbox = collect_inbox(devices, links, device_id)
            results[device_id] = run_round(device, inbox, program)
    return results


@aggregate
def gradient() -> float:
    """Hop count from the source; stores whether the device is more than one hop away."""
    set_distance, distance = remember(INFINITY)
    through_neighbors = neighbors(distance) + 1
    nearest = min(through_neighbors.exclude_self().values(), default=INFINITY)
    set_distance(0 if sense("source") else nearest)
    store("is_far", distance > 1)
    return distance


def line_of_devices(size: int, source: int) -> dict[int, Device]:
    """Devices 0..size-1, with ``source`` as the only source."""
    return {
        device_id: Device(device_id, {"source": device_id == source})
        for device_id in range(size)
    }


def line_links(size: int) -> dict[int, list[int]]:
    """Each device is linked to the previous and the next one."""
    return {
        device_id: [other for other in (device_id - 1, device_id + 1) if 0 <= other < size]
        for device_id in range(size)
    }


def main() -> None:
    """Compute a gradient on a line of five devices and print it."""
    devices = line_of_devices(size=5, source=0)
    print(run_rounds(devices, line_links(size=5), gradient, rounds=6))


if __name__ == "__main__":
    main()

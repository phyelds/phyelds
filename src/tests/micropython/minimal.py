"""
A minimal program, which test_runtime.py runs on MicroPython to keep the heap it needs in
check: a counter and the ids of the neighbors, on three devices exchanging bytes.

    python minimal.py

prints the results of the last round.
"""
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import local_id
from phyelds.vm.device import Device

ROUNDS = 3


@aggregate
def program():
    set_count, count = remember(0)
    set_count(count + 1)
    return neighbors(local_id()).sum()


def run():
    """Run ``program`` on three devices that all hear each other; return the last results."""
    devices = [Device(device_id, program, paths="compact") for device_id in range(3)]
    for _ in range(ROUNDS):
        payloads = [device.run_round({}) for device in devices]
        for device in devices:
            for sender, payload in zip(devices, payloads):
                if sender is not device:
                    device.receive(sender.device_id, payload)
    return [device.result for device in devices]


if __name__ == "__main__":
    print(run())

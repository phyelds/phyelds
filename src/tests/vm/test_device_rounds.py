from phyelds.calculus import aggregate, neighbors, remember
from phyelds.libraries.device import sense, store
from phyelds.vm.device import Device

INFINITY = float("inf")


@aggregate
def gradient():
    set_distance, distance = remember(INFINITY)
    nearest = min((neighbors(distance) + 1).exclude_self().values(), default=INFINITY)
    set_distance(0 if sense("source") else nearest)
    store("is_far", distance > 1)
    return distance


def _run_line(devices: list[Device], rounds: int) -> list:
    for _ in range(rounds):
        payloads = [
            device.run_round({"source": index == 0}) for index, device in enumerate(devices)
        ]
        for index, payload in enumerate(payloads):
            for other in (index - 1, index + 1):
                if 0 <= other < len(devices):
                    devices[other].receive(devices[index].device_id, payload)
    return [device.result for device in devices]


def test_device_computes_a_gradient_when_devices_exchange_bytes():
    devices = [Device(device_id, gradient) for device_id in (10, 20, 30)]

    results = _run_line(devices, rounds=3)

    assert results == [0, 1, 2]
    assert [device.outputs for device in devices] == [
        {"is_far": False}, {"is_far": False}, {"is_far": True}
    ]


def test_device_computes_the_same_values_with_compact_paths():
    devices = [Device(device_id, gradient, paths="compact") for device_id in (10, 20, 30)]

    assert _run_line(devices, rounds=3) == [0, 1, 2]


def test_device_computes_the_same_values_with_an_encoding_of_its_own():
    codes = {"gradient": 1, "remember": 2, "neighbors": 3, "left": 4, "right": 5}

    class Numbered:
        """``gradient@0`` then ``neighbors@1`` as ``"1.0/3.1"``: readable with ``codes``."""

        def segment(self, parent, name, counter):  # pylint: disable=unused-argument
            return f"{codes[name]}.{counter}"

        def key(self, path):
            return "/".join(path)

    devices = [Device(device_id, gradient, paths=Numbered()) for device_id in (10, 20, 30)]

    assert _run_line(devices, rounds=3) == [0, 1, 2]


def test_device_sends_smaller_payloads_in_the_binary_format():
    json, binary = Device(1, gradient), Device(1, gradient, binary=True)

    assert len(binary.run_round({"source": True})) < len(json.run_round({"source": True}))


def test_device_understands_neighbors_that_send_the_other_format():
    devices = [Device(10, gradient, binary=True), Device(20, gradient), Device(30, gradient, binary=True)]

    assert _run_line(devices, rounds=3) == [0, 1, 2]


def test_device_forgets_a_neighbor_silent_for_longer_than_the_lifetime():
    source = Device(1, gradient)
    device = Device(2, gradient, lifetime=2)
    source.run_round({"source": True})  # the first round still shares the initial value
    device.receive(1, source.run_round({"source": True}))

    device.run_round({})
    device.run_round({})
    assert device.result == 1

    device.run_round({})
    assert device.result == INFINITY


def test_device_returns_bytes_to_send():
    assert isinstance(Device(1, gradient).run_round({"source": True}), bytes)

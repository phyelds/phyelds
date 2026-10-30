from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id, sense, store
from phyelds.vm.device import Device

INFINITY = float("inf")


@aggregate
def gradient():
    set_distance, distance = remember(INFINITY)
    nearest = min((neighbors(distance) + 1).exclude_self().values(), default=INFINITY)
    set_distance(0 if sense("source") else nearest)
    store("is_far", distance > 1)
    return distance


@aggregate
def addressed():
    """Sends each neighbor 10 times its id plus its own: what a device receives tells who sent it."""
    set_field, received = exchange(-1)
    own = local_id()
    set_field(NeighborhoodField({other: 10 * other + own for other in received.data}, own, default=-1))
    return dict(received.data)


def _run_line(devices: list[Device], rounds: int) -> list:
    """Rounds on a line, where each device hears every message of the devices next to it."""
    for _ in range(rounds):
        sent = []
        for index, device in enumerate(devices):
            payload = device.run_round({"source": index == 0})
            sent.append([*device.addressed.values(), payload])  # the addressed ones first
        for index, payloads in enumerate(sent):
            for other in (index - 1, index + 1):
                if 0 <= other < len(devices):
                    for payload in payloads:
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


def test_device_sends_each_neighbor_its_own_value_of_a_field():
    whole = [Device(device_id, addressed) for device_id in (10, 20, 30)]
    per_neighbor = [Device(device_id, addressed, per_neighbor=True) for device_id in (10, 20, 30)]

    expected = _run_line(whole, rounds=3)

    assert expected[1] == {10: 210, 20: 220, 30: 230}
    assert _run_line(per_neighbor, rounds=3) == expected


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

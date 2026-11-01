import pytest

from phyelds.calculus import aggregate, exchange, neighbors, remember
from phyelds.data import NeighborhoodField
from phyelds.libraries.device import local_id, sense, store
from phyelds.libraries.time import counter
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


def test_device_sends_smaller_payloads_in_the_binary_format():
    json, binary = Device(1, gradient), Device(1, gradient, binary=True)

    assert len(binary.run_round({"source": True})) < len(json.run_round({"source": True}))


def test_device_understands_neighbors_that_send_the_other_format():
    devices = [Device(10, gradient, binary=True), Device(20, gradient), Device(30, gradient, binary=True)]

    assert _run_line(devices, rounds=3) == [0, 1, 2]


def test_device_sends_each_neighbor_its_own_value_of_a_field():
    shared = [Device(device_id, addressed) for device_id in (10, 20, 30)]
    addressing = [Device(device_id, addressed, messages="addressed") for device_id in (10, 20, 30)]

    expected = _run_line(shared, rounds=3)

    assert expected[1] == {10: 210, 20: 220, 30: 230}
    assert _run_line(addressing, rounds=3) == expected


def test_device_addresses_its_messages_in_the_binary_format_too():
    shared = [Device(device_id, addressed) for device_id in (10, 20, 30)]
    devices = [Device(device_id, addressed, messages="addressed", binary=True) for device_id in (10, 20, 30)]

    assert _run_line(devices, rounds=3) == _run_line(shared, rounds=3)
    assert all(payload[:1] != b"{" for device in devices for payload in device.addressed.values())


def _hear(device: Device, sender: Device) -> None:
    """A round of ``sender``, all of whose messages ``device`` hears, the addressed ones first."""
    payload = sender.run_round({})
    for message in [*sender.addressed.values(), payload]:
        device.receive(sender.device_id, message)


def test_device_ignores_the_messages_addressed_to_other_devices():
    sender, device, other = (Device(device_id, addressed, messages="addressed") for device_id in (1, 2, 3))
    sender.receive(2, device.run_round({}))
    sender.receive(3, other.run_round({}))

    payload = sender.run_round({})
    for message in [payload, sender.addressed[2], sender.addressed[3]]:
        device.receive(1, message)
    device.run_round({})

    assert device.result[1] == 21


def test_device_takes_the_message_for_every_neighbor_once_none_is_addressed_to_it():
    sender = Device(1, addressed, messages="addressed", lifetime=1)
    device = Device(2, addressed, messages="addressed")
    sender.receive(2, device.run_round({}))
    _hear(device, sender)
    device.run_round({})
    assert device.result[1] == 21

    _hear(device, sender)  # it no longer hears the device, so it addresses it nothing
    device.run_round({})

    assert device.result[1] == -1


def test_device_addresses_no_message_when_its_program_sends_no_field():
    devices = [Device(device_id, gradient, messages="addressed") for device_id in (10, 20, 30)]

    _run_line(devices, rounds=3)

    assert [device.addressed for device in devices] == [{}, {}, {}]


def _payload_sizes(neighbors: int, messages: str) -> list[int]:
    center = Device(0, addressed, messages=messages)
    for neighbor in range(1, neighbors + 1):
        center.receive(neighbor, Device(neighbor, addressed).run_round({}))
    payload = center.run_round({})
    return [len(payload), *map(len, center.addressed.values())]


def test_device_messages_do_not_grow_with_the_neighbors_when_addressed():
    assert max(_payload_sizes(8, "addressed")) == max(_payload_sizes(2, "addressed"))
    assert max(_payload_sizes(8, "shared")) > max(_payload_sizes(2, "shared"))


def test_device_rejects_messages_other_than_shared_and_addressed():
    with pytest.raises(ValueError, match="messages"):
        Device(1, gradient, messages="per_neighbor")


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


def test_device_snapshot_is_bytes():
    device = Device(1, gradient)
    device.run_round({"source": True})

    assert isinstance(device.snapshot(), bytes)


@aggregate
def counted_gradient():
    """The gradient, and the rounds the device has run: a state it would lose on a restart."""
    return gradient().value, counter().value


def _alone(device: Device, rounds: int) -> list:
    """Rounds of ``device`` that hear nothing new: what it sends and computes from what it holds."""
    return [(device.run_round({}), device.result) for _ in range(rounds)]


@pytest.mark.parametrize("options", [{}, {"paths": "compact", "binary": True}])
def test_device_restored_from_a_snapshot_runs_on_as_the_original(options):
    devices = [Device(device_id, counted_gradient, lifetime=2, **options) for device_id in (10, 20, 30)]
    _run_line(devices, rounds=2)
    original = devices[1]
    original.run_round({})  # the messages it holds are a round old, and expire a round later
    restored = Device(20, counted_gradient, lifetime=2, **options)

    restored.restore(original.snapshot())

    assert _alone(restored, rounds=3) == _alone(original, rounds=3)


def test_device_rejects_a_message_in_place_of_a_snapshot():
    device = Device(1, gradient)

    with pytest.raises(ValueError, match="snapshot"):
        device.restore(Device(2, gradient).run_round({}))

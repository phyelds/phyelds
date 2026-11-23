from phyelds.ros2.message import pack, unpack


def test_unpack_gives_back_what_pack_took():
    data = pack("robot1", {"position": [1.0, 2.0, 0.0]}, b"\x00payload\nwith newline")

    sender, header, payload = unpack(data)

    assert sender == "robot1"
    assert header == {"position": [1.0, 2.0, 0.0]}
    assert payload == b"\x00payload\nwith newline"

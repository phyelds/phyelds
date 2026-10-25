"""A host can supply radio geometry instead of absolute positions."""
import pytest

from phyelds.calculus import aggregate
from phyelds.experimental.swarm import Vector, neighbors_vectors
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.vm.device import Device


@pytest.mark.parametrize("query,sensor,measurement,zero", [
    (neighbors_distances, "neighbors_distances", 1.25, 0.0),
    (neighbors_vectors, "neighbors_vectors", (0.75, 1.0), Vector()),
])
def test_measured_geometry_works_without_position(query, sensor, measurement, zero):
    devices = [Device(node_id, query) for node_id in (0, 1)]
    sensors = {sensor: {0: measurement, 1: measurement, 99: measurement}}
    for _ in range(2):
        payloads = [device.run_round(sensors) for device in devices]
        devices[0].receive(1, payloads[1])
        devices[1].receive(0, payloads[0])

    expected = measurement if sensor == "neighbors_distances" else Vector(*measurement)
    assert devices[0].result.data == {0: zero, 1: expected}


@aggregate
def _conditional_geometry():
    if sense("active"):
        return neighbors_distances().data, neighbors_vectors().data
    return None


def test_measured_geometry_excludes_neighbors_on_another_branch_and_lost_neighbors():
    active = Device(0, _conditional_geometry)
    inactive = Device(1, _conditional_geometry)
    sensors = {"active": True, "neighbors_distances": {1: 2.0}, "neighbors_vectors": {1: (2, 0)}}
    for _ in range(2):
        payload = inactive.run_round({"active": False})
        active.receive(1, payload)
        active.run_round(sensors)
    assert active.result == ({0: 0.0}, {0: Vector()})

    peer = Device(2, _conditional_geometry)
    payload = peer.run_round({**sensors, "neighbors_distances": {}, "neighbors_vectors": {}})
    active.receive(2, payload)
    active.run_round({**sensors, "neighbors_distances": {2: 3.0}, "neighbors_vectors": {2: (0, 3)}})
    assert active.result == ({0: 0.0, 2: 3.0}, {0: Vector(), 2: Vector(0, 3)})
    active.run_round({**sensors, "neighbors_distances": {}, "neighbors_vectors": {}})
    assert active.result == ({0: 0.0}, {0: Vector()})


def test_explicit_position_takes_precedence_over_measured_geometry():
    def program():
        return neighbors_distances((1, 2)).data, neighbors_vectors((1, 2)).data

    device = Device(0, program)
    device.run_round({"neighbors_distances": {0: 9}, "neighbors_vectors": {0: (9, 9)}})
    assert device.result == ({0: 0.0}, {0: Vector()})

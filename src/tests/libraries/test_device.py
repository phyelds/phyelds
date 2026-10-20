import math

import pytest

from phyelds import engine
from phyelds.vm.internal import MutableEngine
from phyelds.libraries.device import Actuator, Sensor, local_id, local_position, sense, store, velocity
from tests.calculus.mock import MockNodeContext


@pytest.fixture(scope="function", autouse=True)
def setup_engine():
    engine.set(MutableEngine().setup(MockNodeContext(0)))

def test_local_id_should_be_coherent():
    assert local_id() == 0

def test_position_should_be_coherent():
    assert local_position() == (0, 0)

def test_sense_should_be_coherent():
    assert sense("position") == (0, 0)
    assert sense("foo") == "bar"

def test_store_should_store_information():
    store("foo", "bar")
    assert engine.get().node_context.outputs["foo"] == "bar"


def test_sensor_sense_reads_the_sensor_of_its_name():
    foo: Sensor[str] = Sensor("foo")

    assert foo.sense() == "bar"


def test_actuator_send_stores_the_value_under_its_name():
    led: Actuator[bool] = Actuator("led")

    led.send(True)

    assert engine.get().node_context.outputs["led"] is True


def test_actuator_read_gives_what_a_program_sent():
    velocity.send((1.0, 2.0))

    assert velocity.read(engine.get().node_context.outputs) == (1.0, 2.0)


def test_actuator_read_gives_the_default_when_nothing_was_sent():
    assert Actuator("led").read({}) is None
    assert Actuator("led").read({}, False) is False


def test_actuator_send_rejects_a_value_its_check_refuses():
    servo: Actuator[float] = Actuator("servo", check=lambda angle: 0 <= angle <= 180)

    with pytest.raises(ValueError, match="servo"):
        servo.send(200)

    assert "servo" not in engine.get().node_context.outputs


@pytest.mark.parametrize("value", [(1.0, math.nan), (math.inf, 0.0), ("1", "2"), 3.0, None])
def test_velocity_rejects_anything_but_finite_numbers(value):
    with pytest.raises(ValueError, match="velocity"):
        velocity.send(value)


def test_actuator_send_returns_what_it_sent_so_a_program_can_return_its_action():
    led: Actuator[bool] = Actuator("led")

    assert led.send(True) is True

import pytest

from phyelds import engine
from phyelds.internal import MutableEngine
from phyelds.libraries.device import local_id, local_position, sense, store
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
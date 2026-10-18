import math
import random
from dataclasses import dataclass

import pytest

from phyelds import engine
from phyelds.calculus import aggregate, neighbors, remember
from phyelds.data import NeighborhoodField, State
from phyelds.data.codec import decode, encode, register
from phyelds.libraries.collect import collect_with, point_to_point
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.gossip import gossip, path_coherent_gossip
from phyelds.libraries.leader_election import candidacy, elect_leader
from phyelds.libraries.spreading import distance_to
from phyelds.libraries.time import time_replicated
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vm.internal import MutableEngine
from tests.calculus.mock import MockNodeContext
from tests.libraries.simulator_utils import setup_up_simulator


@dataclass(frozen=True)
class Reading:
    sensor: str
    value: float = 0.0


register(Reading)
NOTHING = register(object(), "test_codec.nothing")


def _round_trip(value):
    return decode(encode({"key": value}))["key"]


@pytest.mark.parametrize("value", [None, True, 3, -2.5, "text", [1, [2, "x"]], (1, (2.0, None))])
def test_codec_round_trips_plain_values(value):
    assert _round_trip(value) == value
    assert type(_round_trip(value)) is type(value)


def test_codec_encodes_to_bytes():
    assert isinstance(encode({"key": 1}), bytes)


def test_codec_round_trips_non_finite_floats():
    infinite, minus_infinite, not_a_number = _round_trip((math.inf, -math.inf, math.nan))

    assert (infinite, minus_infinite) == (math.inf, -math.inf)
    assert math.isnan(not_a_number)


def test_codec_keeps_the_type_of_dictionary_keys():
    assert decode(encode({7: {1: "a", "1": "b", (2, 3): "c"}})) == {7: {1: "a", "1": "b", (2, 3): "c"}}


def test_codec_round_trips_sets():
    assert _round_trip({1, 2}) == {1, 2}


def test_codec_round_trips_neighborhood_fields_with_their_default():
    field = NeighborhoodField({2: 1.5, 1: 0.5}, 1, default=math.inf)

    decoded = _round_trip(field)

    assert (decoded.data, decoded.node_id, decoded.default) == ({1: 0.5, 2: 1.5}, 1, math.inf)


def test_codec_round_trips_registered_dataclasses():
    assert _round_trip(Reading("temperature", 21.5)) == Reading("temperature", 21.5)


def test_codec_restores_registered_constants_by_identity():
    assert _round_trip([NOTHING])[0] is NOTHING


def test_codec_sends_the_value_of_a_state():
    @aggregate
    def program():
        _, state = remember(4)
        return state

    engine.set(MutableEngine().setup(MockNodeContext(0)))
    state = program()

    assert isinstance(state, State)
    assert type(_round_trip(state)) is int


def test_codec_rejects_unregistered_types():
    class Unknown:
        pass

    with pytest.raises(TypeError, match="Unknown"):
        encode({"key": Unknown()})


def test_codec_rejects_constants_registered_without_a_name():
    with pytest.raises(ValueError, match="name"):
        register(object())


def test_codec_round_trips_the_outbox_of_an_engine():
    @aggregate
    def program():
        return neighbors((1, math.inf))

    engine.set(MutableEngine(paths="compact").setup(MockNodeContext(0)))
    program()
    outbox = engine.get().cooldown()

    assert decode(encode(outbox)) == outbox


@aggregate
def _collected():
    potential = distance_to(sense("source"), hops_distance())
    return collect_with(potential, 1, lambda a, b: a + b, strategy=point_to_point())


@aggregate
def _path_coherent_maximum():
    return gossip(local_id(), max, strategy=path_coherent_gossip())


@aggregate
def _replicated_minimum():
    return time_replicated(lambda: gossip(local_id(), min), 3)


@aggregate
def _leader():
    return elect_leader(2, strategy=candidacy(local_id()))


def _results(program) -> list:
    random.seed(0)
    simulator = setup_up_simulator(5)
    simulator.environment.nodes[0].update(new_data={"source": True})
    schedule_program_for_all(simulator, 0.0, 1.0, program)
    simulator.run(10)
    return [node.data["result"] for node in simulator.environment.nodes.values()]


@pytest.mark.parametrize(
    "program", [_collected, _path_coherent_maximum, _replicated_minimum, _leader]
)
def test_codec_carries_the_messages_of_the_libraries(program, monkeypatch):
    expected = _results(program)
    cooldown = MutableEngine.cooldown
    monkeypatch.setattr(MutableEngine, "cooldown", lambda self: decode(encode(cooldown(self))))

    assert _results(program) == expected

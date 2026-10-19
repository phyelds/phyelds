import pytest

from phyelds._mpy.dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    __dataclass_fields__ = ("sensor", "value", "scale")
    value = 0.0
    scale = lambda x: x  # noqa: E731  (a callable default must not become a method)


@dataclass
class Counter:
    __dataclass_fields__ = ("count",)

    def __post_init__(self):
        self.doubled = self.count * 2


def test_dataclass_fills_fields_from_arguments_and_defaults():
    reading = Reading("temperature", scale=abs)

    assert (reading.sensor, reading.value, reading.scale) == ("temperature", 0.0, abs)


def test_dataclass_keeps_callable_defaults_as_they_are():
    assert Reading("temperature").scale(3) == 3


def test_dataclass_compares_and_hashes_by_fields_when_frozen():
    assert Reading("a", 1.0) == Reading("a", 1.0)
    assert Reading("a", 1.0) != Reading("a", 2.0)
    assert len({Reading("a", 1.0), Reading("a", 1.0)}) == 1


def test_dataclass_shows_its_fields():
    assert repr(Counter(2)) == "Counter(2,)"


def test_dataclass_runs_post_init():
    assert Counter(2).doubled == 4


def test_dataclass_rejects_a_missing_field():
    with pytest.raises(TypeError, match="sensor"):
        Reading()

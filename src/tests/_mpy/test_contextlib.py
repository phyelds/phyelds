import pytest

from phyelds._mpy.contextlib import contextmanager


@contextmanager
def recording(events):
    events.append("enter")
    yield "value"
    events.append("exit")


def test_contextmanager_runs_the_generator_around_the_block():
    events = []

    with recording(events) as value:
        events.append(value)

    assert events == ["enter", "value", "exit"]


def test_contextmanager_lets_exceptions_through():
    events = []

    with pytest.raises(KeyError):
        with recording(events):
            raise KeyError("boom")

    assert events == ["enter"]

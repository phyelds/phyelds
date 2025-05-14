import pytest
from phyelds.data import State
from unittest.mock import MagicMock

def updates_value_with_none():
    engine = MagicMock()
    s = State(default=0, path=['x'], engine=engine)
    s.update(None)
    assert s.value is None
    engine.write_state.assert_called_with(None, ['x'])

def update_fn_with_update_function():
    engine = MagicMock()
    s = State(default=5, path=['y'], engine=engine)
    s.update_fn(lambda x: x + 1)
    assert s.value == 6
    engine.write_state.assert_called_with(5, ['y'])

def forget_on_already_none_value():
    engine = MagicMock()
    s = State(default=None, path=['a'], engine=engine)
    s.forget()
    assert s.value is None
    engine.forget.assert_called_with(['a'])

def str_and_repr_with_none_value():
    engine = MagicMock()
    s = State(default=None, path=['b'], engine=engine)
    assert str(s) == "None"
    assert repr(s) == "State: None"

def copy_and_deepcopy_preserve_path_and_engine():
    engine = MagicMock()
    s = State(default=3, path=['c'], engine=engine)
    s2 = s.__copy__()
    s3 = s.__deepcopy__({})
    assert s2._self_path == ['c']
    assert s3._self_path == ['c']
    assert s2._self_engine is engine
    assert s3._self_engine is engine

def reduce_and_reduce_ex_with_none_value():
    engine = MagicMock()
    s = State(default=None, path=['d'], engine=engine)
    assert s.__reduce__() is None
    assert s.__reduce_ex__(0) is None
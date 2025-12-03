from unittest.mock import MagicMock

from phyelds.data import State

def prepare_engine_mock():
    engine = MagicMock()
    engine.configure_mock(**{'read_state.return_value': None})
    return engine

def test_updates_value_with_none():
    engine = prepare_engine_mock()
    s = State(default=0, path=['x'], engine=engine)
    s.update_fn(None)
    assert s.value is None
    engine.write_state.assert_called_with(None, ['x'])

def test_update_fn_with_update_function():
    engine = prepare_engine_mock()
    s = State(default=5, path=['y'], engine=engine)
    engine.write_state.assert_called_with(5, ['y'])
    s.update_fn(s + 1)
    #print(str(s.value))
    assert s.value == 6
    engine.write_state.assert_called_with(6, ['y'])

def test_str_and_repr_with_none_value():
    engine = prepare_engine_mock()
    s = State(default=None, path=['b'], engine=engine)
    assert str(s) == "None"
    assert repr(s) == "State: None"

def test_copy_and_deepcopy_preserve_path_and_engine():
    engine = prepare_engine_mock()
    s = State(default=3, path=['c'], engine=engine)
    s2 = s.__copy__()
    s3 = s.__deepcopy__({})
    assert s2._self_path == ['c']
    assert s3._self_path == ['c']
    assert s2._self_engine is engine
    assert s3._self_engine is engine

def test_reduce_and_reduce_ex_with_none_value():
    engine = prepare_engine_mock()
    s = State(default=None, path=['d'], engine=engine)
    assert s.__reduce__() is None
    assert s.__reduce_ex__(0) is None
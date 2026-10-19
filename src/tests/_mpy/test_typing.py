from phyelds._mpy import abc, functools, typing


def test_typing_names_stand_for_any_type():
    alias = typing.Callable[[typing.Any], int | None]

    assert typing.TypeVar("T") is alias is (typing.Optional | None)
    assert typing.cast(alias, 3) == 3


def test_stand_ins_without_logic_leave_their_arguments_alone():
    def function():
        return 1

    assert functools.wraps(function)(len) is len
    assert functools.update_wrapper(len, function) is len
    assert abc.abstractmethod(function) is function
    assert isinstance(type("Base", (abc.ABC,), {})(), abc.ABC)

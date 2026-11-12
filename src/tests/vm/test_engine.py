"""
The engine interface: the operations an engine implements fail loudly where it does not.
"""
import pytest

from phyelds.vm import Engine


@pytest.mark.parametrize(
    "operation, arguments",
    [
        ("setup", (None, {})),
        ("enter", ("point",)),
        ("exit", ()),
        ("current_path", ()),
        ("write_state", (1,)),
        ("read_state", ()),
        ("state_trace", ()),
        ("forget", ([],)),
        ("send", (1,)),
        ("aligned", ()),
        ("aligned_values", ()),
        ("begin_process", ("process",)),
        ("end_process", (None, True)),
        ("cooldown", ()),
    ],
)
def test_engine_raises_for_an_operation_it_does_not_implement(operation, arguments):
    with pytest.raises(NotImplementedError):
        getattr(Engine(), operation)(*arguments)

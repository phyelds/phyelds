from phyelds._mpy.enum import Enum, members


@members
class Status(Enum):
    ON = "on"
    OFF = "off"

    def describe(self):
        return f"is {self.value}"


def test_members_turns_attributes_into_members():
    assert (Status.ON.name, Status.ON.value) == ("ON", "on")
    assert isinstance(Status.OFF, Status)
    assert Status.ON is not Status.OFF


def test_members_keeps_methods():
    assert Status.ON.describe() == "is on"
    assert repr(Status.ON) == "<Status.ON: 'on'>"

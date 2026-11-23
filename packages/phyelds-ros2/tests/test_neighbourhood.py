import pytest

from phyelds.ros2.neighbourhood import Neighbour, Reachable, WithinRange


def test_reachable_admits_any_sender_without_a_distance():
    reachable = Reachable()

    neighbour = reachable.admit(reachable.header(None), None)

    assert neighbour == Neighbour()
    assert neighbour.distance is None and neighbour.vector is None


def test_reachable_measures_a_sender_however_far_when_asked_to():
    reachable = Reachable(measure=True)

    neighbour = reachable.admit(reachable.header((100.0, 0.0, 0.0)), (0.0, 0.0, 0.0))

    assert neighbour == Neighbour(distance=100.0, vector=(100.0, 0.0, 0.0))


def test_reachable_admits_a_sender_unmeasured_when_a_position_is_unknown():
    reachable = Reachable(measure=True)

    neighbour = reachable.admit(reachable.header(None), (0.0, 0.0, 0.0))

    assert neighbour == Neighbour()


def test_within_range_admits_a_sender_in_range_with_its_distance_and_vector():
    within_range = WithinRange(2.0)
    header = within_range.header((1.0, 1.0, 0.0))

    neighbour = within_range.admit(header, (0.0, 1.0, 0.0))

    assert neighbour == Neighbour(distance=1.0, vector=(1.0, 0.0, 0.0))


@pytest.mark.parametrize(("there", "admitted"), [((2.5, 0.0, 0.0), False), ((2.0, 0.0, 0.0), True)])
def test_within_range_admits_a_sender_only_up_to_its_radius(there, admitted):
    within_range = WithinRange(2.0)

    neighbour = within_range.admit(within_range.header(there), (0.0, 0.0, 0.0))

    assert (neighbour is not None) == admitted


@pytest.mark.parametrize(("there", "here"), [(None, (0.0, 0.0, 0.0)), ((0.0, 0.0, 0.0), None)])
def test_within_range_admits_no_sender_when_a_position_is_unknown(there, here):
    within_range = WithinRange(2.0)

    neighbour = within_range.admit(within_range.header(there), here)

    assert neighbour is None

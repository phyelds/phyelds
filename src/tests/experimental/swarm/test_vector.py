import math

import pytest

from phyelds.data.codec import decode, encode
from phyelds.experimental.swarm import Vector


def test_vector_is_zero_without_components():
    assert Vector() == Vector(0.0, 0.0, 0.0)


def test_vector_adds_subtracts_and_negates_component_wise():
    assert Vector(1, 2) + Vector(3, 4, 5) == Vector(4, 6, 5)
    assert Vector(1, 2, 3) - Vector(1, 1, 1) == Vector(0, 1, 2)
    assert -Vector(1, -2) == Vector(-1, 2)


def test_vector_scales_by_a_number_on_either_side():
    assert Vector(1, 2) * 2 == Vector(2, 4)
    assert 2 * Vector(1, 2) == Vector(2, 4)
    assert Vector(2, 4) / 2 == Vector(1, 2)


def test_vector_measures_its_length_in_three_dimensions():
    assert Vector(2, 3, 6).length() == 7.0


def test_vector_normalizes_to_unit_length_keeping_the_direction():
    assert tuple(Vector(0, 3, 4).normalize()) == pytest.approx((0.0, 0.6, 0.8))


def test_vector_normalizes_zero_to_zero():
    assert Vector().normalize() == Vector()


def test_vector_limits_only_a_longer_vector():
    assert tuple(Vector(3, 4).limit(1.0)) == pytest.approx((0.6, 0.8, 0.0))
    assert Vector(0.3, 0.4).limit(1.0) == Vector(0.3, 0.4)


def test_vector_rotates_in_the_horizontal_plane_keeping_the_height():
    rotated = Vector(1, 0, 5).rotate(math.pi / 2)

    assert rotated.x == pytest.approx(0.0, abs=1e-12)
    assert (rotated.y, rotated.z) == (1.0, 5.0)


def test_vector_computes_dot_and_cross_products():
    assert Vector(1, 2, 3).dot(Vector(4, 5, 6)) == 32
    assert Vector(1, 0, 0).cross(Vector(0, 1, 0)) == Vector(0, 0, 1)


def test_vector_unpacks_to_a_position_of_any_dimension():
    assert tuple(Vector(1, 2, 3)) == (1, 2, 3)
    assert Vector(*(1, 2)) == Vector(1, 2, 0)
    assert Vector(1, 2, 3).position(2) == (1, 2)


def test_vector_travels_in_messages():
    assert decode(encode({"v": Vector(1.5, -2, 3)})) == {"v": Vector(1.5, -2, 3)}

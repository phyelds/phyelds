import math

import pytest

from phyelds.experimental.formation import (
    Shape, arc, box, circle, crescent, half_plane, hexagon, polygon, rectangle, regular_polygon,
    rounded_rectangle, segment, square, star,
)
from phyelds.experimental.swarm import Vector


def test_circle_is_the_distance_from_its_border_negative_inside():
    disk = circle((0, 0), 2)

    assert (disk((0, 0)), disk((2, 0)), disk((3, 4))) == (-2.0, 0.0, 3.0)
    assert disk.inside((1, 1)) and not disk.inside((2, 2))


def test_circle_with_a_planar_center_is_a_cylinder_in_space():
    assert circle((0, 0), 2)((0, 0, 5)) == -2.0


def test_circle_with_a_center_in_space_is_a_sphere():
    assert circle((0, 0, 0), 2)((0, 0, 5)) == 3.0


def test_segment_is_the_distance_from_it():
    stroke = segment((0, 0), (4, 0))

    assert (stroke((2, 1)), stroke((-3, 4)), stroke((7, 0))) == (1.0, 5.0, 3.0)


def test_half_plane_is_inside_on_the_left_of_its_direction():
    left = half_plane((0, 0), (1, 0))

    assert (left((5, 2)), left((5, -3))) == (-2.0, 3.0)


def test_box_is_exact_inside_and_out_in_any_dimension():
    assert rectangle((0, 0), 4, 2)((0, 0)) == -1.0
    assert rectangle((0, 0), 4, 2)((5, 4)) == pytest.approx(math.sqrt(9 + 9))
    assert box((0, 0, 0), (2, 2, 2))((0, 0, 3)) == 2.0
    assert square((1, 1), 2)((1, 1)) == -1.0


def test_rounded_rectangle_rounds_the_corners():
    rounded = rounded_rectangle((0, 0), 4, 4, radius=1)

    assert rounded((2, 0)) == 0.0
    assert rounded((2, 2)) == pytest.approx(math.sqrt(2) - 1)


def test_polygon_is_the_signed_distance_from_its_edges():
    triangle = polygon([(0, 0), (4, 0), (0, 4)])

    assert triangle((1, 1)) == -1.0
    assert triangle((-1, 2)) == 1.0
    assert triangle((3, 3)) == pytest.approx(math.sqrt(2))


def test_regular_polygons_have_their_vertices_on_the_radius():
    assert regular_polygon((0, 0), 2, 4)((2, 0)) == pytest.approx(0.0, abs=1e-12)
    assert hexagon((0, 0), 2)((0, 0)) == pytest.approx(-math.sqrt(3))


def test_star_has_its_tips_on_the_radius_and_its_center_inside():
    shape = star((0, 0), 5, 5)

    assert shape((0, 5)) == pytest.approx(0.0, abs=1e-12)
    assert shape((0, 0)) < 0 < shape((0, 6))


def test_arc_is_the_distance_from_the_arc():
    upper = arc((0, 0), 2, 0, math.pi)

    assert upper((0, 3)) == pytest.approx(1.0)
    assert upper((2, -1)) == pytest.approx(1.0)


def test_crescent_is_a_disk_without_another():
    moon = crescent((0, 0), 2, 2)

    assert moon((-1.5, 0)) < 0
    assert moon((1.5, 0)) > 0


def test_operators_combine_shapes():
    left, right = circle((0, 0), 2), circle((3, 0), 2)

    assert (left | right)((3, 0)) == -2.0
    assert (left & right)((1.5, 0)) == -0.5
    assert (~left)((0, 0)) == 2.0
    assert (left - right)((1.5, 0)) == 0.5
    assert left.expand(1)((3, 0)) == 0.0
    assert left.ring(0.5)((0, 0)) == 1.5


def test_transformations_move_the_shape_keeping_distances():
    disk = circle((0, 0), 1)

    assert disk.translate(3, 4)((3, 4)) == -1.0
    assert rectangle((2, 0), 2, 0.5).rotate(math.pi / 2)((0, 2)) == pytest.approx(-0.25)
    assert disk.scale(2, (1, 0))((1, 0)) == pytest.approx(0.0)
    assert disk.scale(2, (1, 0))((-1, 0)) == pytest.approx(-2.0)
    assert disk.scale(2)((0, 0)) == -2.0


def test_shape_takes_any_function_of_a_vector():
    plane = Shape(lambda position: position.z)

    assert plane((1, 2, 3)) == 3.0


def test_gradient_points_away_from_the_shape():
    direction = circle((0, 0), 1).gradient((3, 4)).normalize()

    assert tuple(direction) == pytest.approx((0.6, 0.8, 0.0))


def test_deepest_point_from_outside_reaches_the_center_of_a_disk():
    deepest = circle((5, 5), 2).deepest_point_from((0, 5))

    assert tuple(deepest) == pytest.approx((5, 5, 0), abs=1e-2)


def test_deepest_point_lies_inside_a_hollow_shape():
    ring = circle((0, 0), 3).ring(0.5)

    deepest = ring.deepest_point_from((0, 0))

    assert ring(deepest) == pytest.approx(-0.5, abs=1e-2)


def test_shapes_compose_with_vectors():
    assert circle((0, 0), 1)(Vector(1, 0)) == 0.0

"""
Swarm formations on signed distance functions: the swarm spreads evenly over a shape.

After the Collektive implementation in
https://github.com/angelacorte/experiments-2026-seams-ac-sdf, whose files the comments
cite. A formation separates three concerns: *what* shape to take,
a signed distance function; *where* each robot is with respect to it, the positioning;
and *how* robots move to spread over it, the control.
"""
from phyelds.experimental.formation.actuation import aligned
from phyelds.experimental.formation.control import lattice_velocity, voronoi_centroid
from phyelds.experimental.formation.pipeline import formation
from phyelds.experimental.formation.positioning import (
    Frame,
    global_positioning,
    leader_positioning,
    place_shape,
)
from phyelds.experimental.formation.shapes import (
    Shape,
    arc,
    box,
    circle,
    crescent,
    half_plane,
    hexagon,
    polygon,
    rectangle,
    regular_polygon,
    rounded_rectangle,
    segment,
    square,
    star,
)

__all__ = [
    "Frame",
    "Shape",
    "aligned",
    "arc",
    "box",
    "circle",
    "crescent",
    "formation",
    "global_positioning",
    "half_plane",
    "hexagon",
    "lattice_velocity",
    "leader_positioning",
    "place_shape",
    "polygon",
    "rectangle",
    "regular_polygon",
    "rounded_rectangle",
    "segment",
    "square",
    "star",
    "voronoi_centroid",
]

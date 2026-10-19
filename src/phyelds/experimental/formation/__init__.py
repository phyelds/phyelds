"""
Swarm formations on signed distance functions: the swarm spreads evenly over a shape.

After the Collektive implementation in
https://github.com/angelacorte/experiments-2026-seams-ac-sdf, whose files the comments
cite. A formation separates three concerns: *what* shape to take,
a signed distance function; *where* each robot is with respect to it, the positioning;
and *how* robots move to spread over it, the control.
"""
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
    "Shape",
    "arc",
    "box",
    "circle",
    "crescent",
    "half_plane",
    "hexagon",
    "polygon",
    "rectangle",
    "regular_polygon",
    "rounded_rectangle",
    "segment",
    "square",
    "star",
]

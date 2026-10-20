---
draft: true
---

# Formations

!!! warning "Experimental"
    This is a [study in progress](index.md): its API will probably change.

A formation spreads a swarm evenly over a shape. The shape is a signed distance
function, built and composed in a few lines; each robot finds where it is with respect
to the shape, and moves towards the centroid of its Voronoi cell clipped to the shape,
so that every robot ends up with an equal share of it. This module follows the
[Collektive implementation](https://github.com/angelacorte/experiments-2026-seams-ac-sdf)
of signed-distance formations.

```python
from phyelds.experimental.formation import circle, formation

store("velocity", formation(circle((0, 0), 5), reach=1.5))
```

A formation separates three concerns, each of which can change without the others:

- **what** shape to take: a [signed distance function](#shapes);
- **where** each robot is with respect to it: its [positioning](#positioning);
- **how** robots move to spread over it: the [control](#control).

---

## Shapes

A shape is the signed distance from its border: negative inside, zero on the border,
positive outside. Shapes are built from primitives, combined with operators and
transformed, and the result is a shape again:

```python
from phyelds.experimental.formation import circle, segment, star

disk = circle((0, 0), 5)
ring = disk.ring(1)                                   # a band along the border
crescent = disk - disk.translate(3, 0)                # a disk without another
cross = (segment((-5, -5), (5, 5)) | segment((-5, 5), (5, -5))).expand(1)
```

| | |
| --- | --- |
| Primitives | `circle`, `segment`, `half_plane`, `box`, `rectangle`, `square`, `rounded_rectangle`, `polygon`, `regular_polygon`, `hexagon`, `star`, `arc`, `crescent`; or `Shape(f)` for any function `f` of a `Vector` |
| Operators | `a \| b` union, `a & b` intersection, `~a` complement, `a - b` difference |
| Offsets | `expand(d)` grows the shape by `d` (shrinks it if negative), `ring(w)` is the band of half-width `w` along its border |
| Transformations | `translate(dx, dy)`, `rotate(angle, pivot)`, `scale(factor, pivot)` |
| Queries | `shape(position)`, `inside(position)`, `gradient(position)`, `deepest_point_from(position)` |

Lines, circles and V shapes are shapes too, so the slot formations of other swarm
libraries are a line away:

```python
line = segment((0, 0), (10, 0)).expand(0.5)
circle_formation = circle((0, 0), 5).ring(0.5)
v_shape = (segment((0, 0), (-5, 5)) | segment((0, 0), (5, 5))).expand(0.5)
```

The shape decides how the swarm spreads: over its interior, along its border with
`shape.ring(w)`, or over a band inside it with `shape - shape.expand(-w)`.

**In space.** A shape built from planar coordinates is planar: in space it is a prism
along the vertical axis, so drones at any height take it on. `circle`, `segment` and
`box` built from coordinates in space are a sphere, a capsule and a box; pass
`dimensions=3` to `formation` to spread the swarm in space rather than in the plane.

---

## Positioning

The positioning gives the frame in which a robot evaluates the shape: where it is, and
where its neighbors are. It is a function returning a `Frame`, passed to `formation`:

| Positioning | The robots sense | The frame |
| --- | --- | --- |
| `global_positioning` *(default)* | Their position (the `position` sensor) | The world: the shape stays where it is |
| `leader_positioning` | The displacement of each neighbor, in a frame they share | Centered on a leader, the robot with the lowest id: each robot adds up the displacements along its path from it |
| `anchor_positioning` | Only how far each neighbor is | Fixed by three anchors: each robot trilaterates its position from its path distances to them |

```python
store("velocity", formation(shape, reach=1.5, positioning=leader_positioning))
```

When the swarm builds the frame, the shape is placed on it: the leader finds a point
deep inside the shape and spreads it, so that the leader, or the anchors, which stay
still to hold the frame, lie inside the shape, even a hollow one. `leader_positioning`
takes the sensed displacements as `offsets`, and `anchor_positioning` the measured
distances as `ranges`; both default to what the `position` sensor gives, for the
simulator.

The frame of the anchors may be turned, or mirrored, with respect to the robots, which
do not know their heading: `self_aligned` learns how from the way the robot's own
commands move its estimate, probing the space first:

```python
from phyelds.experimental.formation import anchor_positioning, self_aligned

store("velocity", formation(shape, reach=1.5, positioning=anchor_positioning, actuation=self_aligned))
```

Anchors and self-alignment are planar.

---

## Control

`lattice_velocity` is how robots spread. Inside the shape, a robot heads to the centroid
of its Voronoi cell, the points within `reach` closer to it than to any neighbor, clipped
to the shape: the swarm spreads evenly and keeps off the border. Outside, the shape
pulls the robot in, and its neighbors push it aside, never back out. The speed adapts:
the step shrinks when the direction reverses, and grows back while it holds, so that
robots settle instead of oscillating. `reach` is half the communication range, so that
the neighbors that shape the cell are in range. In the simulator, an
[`adaptive_range`](../simulator.md#ranges-that-adapt) keeps the swarm connected while it
gathers or spreads, as in the example below.

`formation` takes another `control(shape, position, offsets)` if you want one, and the
pieces are public: positioning, `place_shape`, `lattice_velocity`, `aligned` or
`self_aligned` compose by hand as `formation` does.

---

## Example: one shape after another

The shape is a value of the program, so it can change: here with the time, every drone
seeing the same clock, and the swarm follows.

```python
--8<-- "formation.py:formation"
```

![A swarm takes a star, then a ring, then a cross](../assets/formation.gif#only-light){ width="480" }
![A swarm takes a star, then a ring, then a cross](../assets/formation-dark.gif#only-dark){ width="480" }

The complete example is
[`docs/examples/formation.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/formation.py).

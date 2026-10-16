# Neighborhood fields

`neighbors(value)` is the only way devices communicate (the `nbr` construct of
field calculus). It does two things at once:

- it **shares** `value` with the neighbors, who will see it in their next round;
- it **returns** the values the neighbors shared *at the same point of the
  program* in their last round, plus the device's own `value`, as a
  `NeighborhoodField`.

```python
from phyelds.calculus import aggregate, neighbors

@aggregate
def neighborhood_size():
    return sum(neighbors(1))   # neighbors + the device itself
```

[Count the neighbours in the playground](../playground/index.md#example=neighbours){ .md-button }

## Working with a `NeighborhoodField`

A `NeighborhoodField` maps device ids to values. It supports:

| Operation | Result |
| --- | --- |
| `field + 1`, `field * other_field`, `-`, `/`, `//`, `%`, `**`, `&`, `|`, `^`, `~` | element-wise field (with another field: only the ids both have) |
| `field < x`, `<=`, `>` | element-wise field of booleans |
| `for value in field`, `sum(field)`, `min(field)` | iterate over the values, in id order |
| `field.exclude_self()` | a `dict` id → value without the device itself |
| `field.local()` | the device's own value |
| `field.for_node(id)` | the value for `id`, or `field.default` if `id` is not in the field |
| `field.map(fn)` | a new field with `fn` applied to each value |
| `field.select(mask)` | the values whose entry in the boolean field `mask` is true |
| `field.any()`, `field.all()` | whether any / all values are truthy |
| `field.data` | the underlying `dict` id → value |

```python
from phyelds.calculus import aggregate, neighbors
from phyelds.libraries.distances import neighbors_distances

@aggregate
def closest_neighbor_distance():
    distances = neighbors_distances()          # a field of float
    return min(distances.exclude_self().values(), default=float("inf"))
```

## What you can share

Any value can be shared, as long as the platform can deliver it: numbers, tuples,
dictionaries, dataclasses. Two exceptions:

- a `NeighborhoodField` cannot be shared (`neighbors` raises `TypeError`): share a
  plain value computed from it instead;
- in the bundled simulator values are delivered **by reference**, so never mutate
  a value you received (see [pitfalls](../pitfalls.md#mutating-shared-values)).

## Who counts as a neighbor

The platform decides: in the simulator it is the neighborhood function of the
environment (a radius, the k nearest, everyone). On top of that, a device only
sees the neighbors that reached the *same* `neighbors` call in their last round:
that is [alignment](alignment.md).

## `exchange`

`exchange(initial)` combines state evolution and communication in one operator (the
`exchange` construct of exchange calculus). It returns a pair `(set_field, field)`:

- `field` is the `NeighborhoodField` of values received from aligned neighbors in
  their last round and from the device itself in its previous round (or `initial`
  in the first round);
- `set_field(next_value)` sets the value to keep for the device and send to its
  neighbors for the next round, and returns `next_value` without mutating `field`.

Unlike `neighbors`, `set_field` also accepts a `NeighborhoodField`: each neighbor
`j` then receives `next_value.for_node(j)` (falling back to `next_value.default`
for neighbors not listed in `next_value.data`), so a device can send distinct
values to different neighbors.

```python
from phyelds.calculus import aggregate, exchange, neighbors
from phyelds.libraries.device import local_id

@aggregate
def anisotropic_counter():
    ids = neighbors(local_id())
    set_field, field = exchange(0)
    return set_field(field + ids)
```

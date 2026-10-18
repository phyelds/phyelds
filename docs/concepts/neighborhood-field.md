# Neighborhood fields & `exchange`

`neighbors(value)` is the primary way devices communicate (the `nbr` construct of field calculus). It does two things at once:

- it **shares** `value` with the device's neighbors, who will read it in their next round;
- it **returns** the values those neighbors shared *at the same point of the program* in their last round—plus the device's own `value`—as a `NeighborhoodField`.

```python
from phyelds.calculus import aggregate, neighbors

@aggregate
def neighborhood_size():
    return sum(neighbors(1))   # (1)!
```

1. Every device advertises `1`. `neighbors(1)` returns a field with `1` for every aligned neighbor plus `1` for the device itself; `sum(...)` counts how many devices are in the neighborhood (including self).

[Count the neighbours in the playground](../playground/index.md#example=neighbours){ .md-button }

---

## Working with a `NeighborhoodField`

A `NeighborhoodField` maps device IDs to values (`{device_id: value}`) and always includes an entry for the current device (`node_id`).

### Arithmetic, comparisons, and iteration

| Operation | Result |
| --- | --- |
| `field + 1`, `field * other_field`, `-`, `/`, `//`, `%`, `**`, `&`, `\|`, `^`, `~` | Element-wise field (when combining two fields, only IDs present in both are kept) |
| `field < x`, `<=`, `>`, `>=` | Element-wise boolean field |
| `for value in field`, `sum(field)`, `min(field)` | Iterates over values in sorted device ID order |

### Accessing and filtering entries

| Operation | Result |
| --- | --- |
| `field.local()` | The device's own value |
| `field.for_node(id)` | The value for `id`, or `field.default` if `id` is not in the field |
| `field.without_self()` | A new `NeighborhoodField` without the device itself |
| `field.exclude_self()` | A plain `dict` (`id → value`) without the device itself |
| `field.select(mask)` | List of values whose entry in the boolean field `mask` is `True` |
| `field.data` | The underlying `dict` (`id → value`) |

### Transformations and reductions

| Operation | Result |
| --- | --- |
| `field.map(fn)` | A new field with `fn` applied to each value |
| `field.coerce_in(lower, upper)` | A new field with values clamped to `[lower, upper]` |
| `field.replace_matching(replacement, predicate)` | A new field where entries satisfying `predicate` are replaced |
| `field.min(*, include_self=True, default=None, key=None)` | Minimum value (with optional `key` and `default`) |
| `field.max(*, include_self=True, default=None, key=None)` | Maximum value (with optional `key` and `default`) |
| `field.id_of_min(*, include_self=True, key=None)` | Device ID of the minimum entry |
| `field.id_of_max(*, include_self=True, key=None)` | Device ID of the maximum entry |
| `field.sum(*, include_self=True, start=0)`, `field.product(*, include_self=True, start=1)` | Sum or product of the values |
| `field.any(predicate=None, *, include_self=True)` | Whether any value satisfies `predicate` (or is truthy) |
| `field.all(predicate=None, *, include_self=True)` | Primary universal check: whether all values satisfy `predicate` |
| `field.none(predicate=None, *, include_self=True)` | Whether no value satisfies `predicate` |
| `field.count_matching(predicate, *, include_self=True)` | How many values satisfy `predicate` |
| `field.fold(initial, accumulator, *, include_self=True)` | Folds values into a single result starting from `initial` |
| `field.reduce(reducer, *, include_self=True, default=None)` | Reduces values with `reducer`, or returns `default` when empty |

```python
from phyelds.calculus import aggregate
from phyelds.libraries.distances import neighbors_distances

@aggregate
def closest_neighbor_distance():
    distances = neighbors_distances()          # a NeighborhoodField of floats
    return distances.min(include_self=False, default=float("inf"))
```

---

## `exchange`: state and anisotropic communication { #exchange }

While `neighbors(v)` broadcasts the **same** value `v` to every neighbor, `exchange(initial)` combines state evolution and neighbor communication into a single operator (from *Exchange Calculus*) that can send **different values to different neighbors**.

![Comparison between isotropic neighbors(v) and anisotropic exchange(init)](../assets/neighbors-vs-exchange.png#only-light)
![Comparison between isotropic neighbors(v) and anisotropic exchange(init)](../assets/neighbors-vs-exchange-dark.png#only-dark)

`exchange(initial)` returns a pair `(set_field, field)`:

- **`field`** is the `NeighborhoodField` containing the values received from aligned neighbors in their last round and from the device itself in its previous round (or `initial` in the first round);
- **`set_field(next_value)`** sets what to keep for the device and send to neighbors for the next round, and returns `next_value` without mutating `field`.

If you pass a `NeighborhoodField` to `set_field(next_value)`, each neighbor `j` receives `next_value.for_node(j)` (falling back to `next_value.default` if `j` is not in `next_value.data`). This is what powers directed collection strategies like `point_to_point()` and `multi_path()` in `phyelds.libraries.collect`.

```python
from phyelds.calculus import aggregate, exchange, neighbors
from phyelds.libraries.device import local_id

@aggregate
def anisotropic_counter():
    ids = neighbors(local_id())
    set_field, field = exchange(0)
    return set_field(field + ids)   # each neighbor j receives field[j] + j
```

---

## What you can share & who is a neighbor

Any serializable value can be shared: numbers, strings, tuples, dictionaries, or dataclasses. Keep two rules in mind:

- **Never pass a `NeighborhoodField` into `neighbors(...)`**: `neighbors` raises `TypeError` because a `NeighborhoodField` is only meaningful on the device that constructed it. Share a plain value computed from it instead (`field.min()`, `field.local()`, etc.).
- **Never mutate a value received from a neighbor**: in the bundled simulator, messages are passed by reference for speed (see [Common pitfalls](../pitfalls.md#mutating-shared-values)).

Who counts as a physical neighbor is determined by the platform or simulator environment (for example, `radius_neighborhood(1.5)` or `k_nearest_neighbors(4)`). Among those physical neighbors, a device only sees the ones that executed the **same** `neighbors` / `exchange` call in their last round—a property known as [alignment](alignment.md).

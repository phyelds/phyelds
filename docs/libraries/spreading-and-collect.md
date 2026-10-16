# Spreading, collection & gossip

This page covers the core spatial propagation libraries: **Spreading (`G`)**, **Collection (`C`)**, and **Gossip**.

---

## Spreading: `phyelds.libraries.spreading`

Spreading functions propagate distances and data **outward** from one or more `source` devices (where `source` is `True`).

| Function | Returns |
| --- | --- |
| `distance_to(source, distances=None, *, strategy=None)` | The gradient: shortest distance from the nearest device where `source` is `True` |
| `broadcast(source, data, distances=None, *, strategy=None)` | The `data` of the nearest `source`, propagated outward along the gradient |
| `cast_from(source, data, accumulation, distances=None, *, strategy=None)` | Like `broadcast`, applying `accumulation(current, step_dist)` at each hop |
| `distance_between(source, target, distances=None, *, strategy=None)` | The shortest distance between `source` and `target`, broadcast across the network |
| `channel(source, target, width=0.0, distances=None, *, strategy=None)` | `True` on devices within `width` of the shortest path between `source` and `target` |

When `distances` is omitted, `hops_distance()` (1 per hop) is used; pass `neighbors_distances()` for metric Euclidean distances.

### Choosing a spreading strategy: `bellman_ford` vs. `path_coherent`

All spreading functions accept a pluggable `strategy`:

- **`bellman_ford()`** *(default)*: classic Bellman-Ford relaxation using `remember` and `neighbors`. Lightweight, but suffers from the *rising-value problem* when all sources disappear or jump far away (stale low estimates slowly count up).
- **`path_coherent(max_diameter=...)`**: fast self-healing gradient built on [`exchange`](../concepts/neighborhood-field.md#exchange) and loop-free `PathValue` routes. When a source disappears, any route that previously depended on it is invalidated immediately instead of looping through neighbors.

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import broadcast, path_coherent

@aggregate
def nearest_station_id():
    # Every device learns the ID of the nearest station via a fast self-healing gradient
    return broadcast(
        sense("is_station"),
        local_id(),
        neighbors_distances(),
        strategy=path_coherent(max_diameter=20),
    )
```

---

## Collection: `phyelds.libraries.collect`

Collection (`C`) is the dual of spreading: values flow **inward** (downhill along a `potential` field, such as a gradient) toward the source(s), accumulating along the way.

| Function | Returns (at the sink: aggregated over the whole basin) |
| --- | --- |
| `find_parent(potential)` | The ID of the neighbor with the lowest `potential` (`None` at a local minimum) |
| `find_parents(potential, predicate=None)` | The `set` of all neighbor IDs whose `potential` is strictly lower than the device's own |
| `collect_with(potential, local, accumulation, *, strategy=None)` | `local` values accumulated downhill with `accumulation(a, b)` |
| `count_nodes(potential, *, strategy=None)` | Total number of devices in the basin |
| `sum_values(potential, local, *, strategy=None)` | Sum of `local` over all devices in the basin |
| `mean_values(potential, local, *, strategy=None)` | Arithmetic mean of `local` over all devices in the basin |
| `collect_or(potential, local, *, strategy=None)` | `True` on nodes whose subtree contains at least one device with `local == True` |
| `summarize(sink, local, accumulation, distances=None, ...)` | Collects `local` into `sink` and broadcasts the aggregated result back to all devices (`G → C → G`) |

### Choosing a collection strategy

Collection functions support three pluggable routing strategies:

<div class="ph-figure">
<svg viewBox="0 0 780 190" role="img" aria-label="Single-parent tree collection versus multi-path DAG collection">
  <defs>
    <marker id="ph-col-o" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-orange)" />
    </marker>
    <marker id="ph-col-m" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-magenta)" />
    </marker>
  </defs>

  <!-- Left: Single-Parent Tree -->
  <rect x="12" y="10" width="368" height="170" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="196" y="32" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ph-diag-orange)">SINGLE-PARENT TREE (point_to_point)</text>

  <circle cx="80" cy="112" r="22" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-orange)" stroke-width="2" />
  <text x="80" y="110" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-text)">Leaf</text>
  <text x="80" y="123" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-orange)">10</text>

  <line x1="104" y1="112" x2="166" y2="112" stroke="var(--ph-diag-orange)" stroke-width="2" marker-end="url(#ph-col-o)" />
  <text x="135" y="103" text-anchor="middle" font-size="10.5" font-weight="700" class="ph-code" fill="var(--ph-diag-orange)">+10</text>

  <circle cx="194" cy="112" r="22" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-orange)" stroke-width="2" />
  <text x="194" y="110" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-text)">Parent</text>
  <text x="194" y="123" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-orange)">10+1</text>

  <line x1="218" y1="112" x2="280" y2="112" stroke="var(--ph-diag-orange)" stroke-width="2" marker-end="url(#ph-col-o)" />
  <text x="249" y="103" text-anchor="middle" font-size="10.5" font-weight="700" class="ph-code" fill="var(--ph-diag-orange)">+11</text>

  <circle cx="308" cy="112" r="22" fill="#c55308" />
  <text x="308" y="116" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Sink</text>

  <!-- Right: Multi-Path DAG -->
  <rect x="400" y="10" width="368" height="170" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="584" y="32" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ph-diag-magenta)">MULTI-PATH DAG (multi_path)</text>

  <circle cx="465" cy="112" r="22" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-magenta)" stroke-width="2" />
  <text x="465" y="110" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-text)">Leaf</text>
  <text x="465" y="123" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-magenta)">10</text>

  <line x1="488" y1="100" x2="556" y2="76" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-col-m)" />
  <text x="518" y="78" text-anchor="middle" font-size="10" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">5.0</text>

  <line x1="488" y1="124" x2="556" y2="148" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-col-m)" />
  <text x="518" y="152" text-anchor="middle" font-size="10" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">5.0</text>

  <circle cx="584" cy="70" r="20" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-magenta)" stroke-width="2" />
  <text x="584" y="74" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-text)">Par A</text>

  <circle cx="584" cy="154" r="20" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-magenta)" stroke-width="2" />
  <text x="584" y="158" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-text)">Par B</text>

  <line x1="606" y1="78" x2="672" y2="102" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-col-m)" />
  <line x1="606" y1="146" x2="672" y2="122" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-col-m)" />

  <circle cx="700" cy="112" r="22" fill="#b4136f" />
  <text x="700" y="116" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Sink</text>
</svg>
</div>

- **`broadcast_collect()`** *(default)*: each node selects its single best parent (`find_parent(potential)`) and advertises `(parent_id, total)` via `neighbors`.
- **`point_to_point()`**: uses an anisotropic [`exchange`](../concepts/neighborhood-field.md#exchange) so each device sends its accumulated total **only** to its selected parent and `identity` to everyone else.
- **`multi_path()`**: builds a Directed Acyclic Graph (DAG) toward all downhill neighbors (`find_parents(potential)`) and splits each node's value equally (`1 / len(parents)`) across all parents using `divider`. More resilient to link changes than a single spanning tree.

```python
from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes, point_to_point
from phyelds.libraries.device import sense
from phyelds.libraries.spreading import distance_to

@aggregate
def network_size():
    potential = distance_to(sense("source"))
    return count_nodes(potential, strategy=point_to_point())
```

### Combining Spreading + Collection: `channel`

Combining two gradients and `collect_or` creates a self-healing communication corridor between `source` and `target`:

![A self-organizing channel between bottom-left and top-right corners](../assets/channel.gif){ width="480" }

[Run the channel in the playground](../playground/index.md#example=channel){ .md-button }

---

## Gossip: `phyelds.libraries.gossip`

Gossip functions compute global extrema or consensus across the network **without** requiring a source or a gradient.

| Function | Returns |
| --- | --- |
| `gossip_min(value, *, key=None, strategy=None)` | The minimum of `value` across the network |
| `gossip_max(value, *, key=None, strategy=None)` | The maximum of `value` across the network |
| `gossip_mean(value)` | Iterative local neighborhood averaging of `value` |
| `gossip(value, callback, *, strategy=None)` | Combines `value` across the network using an associative, idempotent `callback` (e.g., `set.union`) |
| `any_node(condition, *, strategy=None)` | Whether `condition` holds on at least one device in the network |
| `stabilizing_gossip(value, max_diameter, callback)` | Hop-bounded gossip that forgets contributions farther than `max_diameter` hops |

### Choosing a gossip strategy

- **`monotonic_gossip()`** *(default)*: fast 1-state gossip (`remember` + `neighbors`). Note that monotonic gossip never forgets an extreme value (e.g., if the node holding the global minimum leaves, its minimum remains in the network).
- **`path_coherent_gossip(max_diameter=...)`**: spatial self-stabilizing gossip based on loop-free `PathValue` routes. Immediately adapts when values increase or devices leave.
- **`time_replicated_gossip(period, max_replicas=2)`**: temporal self-stabilizing gossip that runs overlapping time-windowed replicas and periodically discards obsolete values.

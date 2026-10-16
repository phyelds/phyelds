# Libraries

`phyelds.libraries` collects reusable aggregate functions, all written with the
same primitives you use. Reading their source is a good way to learn idiomatic
phyelds. All of them must be called from inside an aggregate program.

## Device: `phyelds.libraries.device`

| Function | Returns |
| --- | --- |
| `local_id()` | the id of the device |
| `local_position()` | its position |
| `sense(name)` | the value of sensor `name` (`None` if missing) |
| `store(name, value)` | writes an output, for the platform to read (actuation, metrics) |

## Distances: `phyelds.libraries.distances`

| Function | Returns |
| --- | --- |
| `neighbors_distances(position=None)` | a field with the Euclidean distance to each neighbor (supports 2D, 3D and N-D coordinates; defaults to `local_position()`) |
| `hops_distance()` | a field with 1 for each neighbor and 0 for the device itself |

## Spreading: `phyelds.libraries.spreading`

| Function | Returns |
| --- | --- |
| `distance_to(source, distances=None, *, strategy=None)` | the gradient: distance from the nearest device where `source` is true |
| `distance_between(source, target, distances=None, *, strategy=None)` | the shortest distance between `source` and `target`, broadcast across the network |
| `channel(source, target, width=0.0, distances=None, *, strategy=None)` | `True` on devices within `width` of the shortest path between `source` and `target` |
| `broadcast(source, data, distances=None, *, strategy=None)` | the `data` of the nearest source, spread along the gradient |
| `cast_from(source, data, accumulation, distances=None, *, strategy=None)` | like `broadcast`, applying `accumulation` at each hop |

When `distances` is omitted, `hops_distance()` is used. Spreading functions accept a
pluggable `strategy`:

- `bellman_ford()` (default): classic Bellman-Ford gradient;
- `path_coherent(max_diameter=...)`: fast self-healing gradient built on `exchange` and
  `PathValue` that avoids the rising-value problem when sources move or disappear.

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import broadcast, path_coherent

@aggregate
def leader_id():
    # every device learns the id of the nearest source via a fast self-healing gradient
    return broadcast(
        sense("source"),
        local_id(),
        neighbors_distances(),
        strategy=path_coherent(max_diameter=20),
    )
```

## Collection: `phyelds.libraries.collect`

Collection is the dual of spreading: values flow *towards* the source along the
gradient (the `potential`), and are accumulated on the way.

| Function | Returns (at the source: over the whole network) |
| --- | --- |
| `find_parent(potential)` | the id of the neighbor with the lowest potential (`None` at a local minimum) |
| `find_parents(potential, predicate=None)` | the `set` of all neighbor ids with potential lower than the device's own |
| `collect_with(potential, local, accumulation, *, strategy=None)` | `local` values accumulated with `accumulation` |
| `count_nodes(potential, *, strategy=None)` | the number of devices |
| `sum_values(potential, local, *, strategy=None)` | the sum of `local` |
| `mean_values(potential, local, *, strategy=None)` | the arithmetic mean of `local` |
| `collect_or(potential, local, *, strategy=None)` | whether any device has `local` true |
| `summarize(sink, local, accumulation, distances=None, ...)` | collects `local` into `sink` and broadcasts the aggregated value back out (`G -> C -> G`) |

Collection functions accept a pluggable `strategy`: `broadcast_collect()` (default,
using `remember` + `neighbors`), `point_to_point()` (using an anisotropic
`exchange` that sends data only to the selected parent), or `multi_path()` (which
splits each device's contribution equally across all parents in the DAG).

```python
from phyelds.libraries.collect import count_nodes, point_to_point
from phyelds.libraries.spreading import distance_to

@aggregate
def network_size():
    potential = distance_to(sense("source"))
    return count_nodes(potential, strategy=point_to_point())
```

The [channel](../playground/index.md#example=channel) of the playground combines
both: a collection of `collect_or` along one gradient, spread again by another.

## Gossip: `phyelds.libraries.gossip`

| Function | Returns |
| --- | --- |
| `gossip_min(value, *, key=None, strategy=None)`, `gossip_max(value, *, key=None, strategy=None)` | the minimum / maximum of `value` over the network |
| `gossip_mean(value)` | local neighborhood averaging of `value` |
| `gossip(value, callback, *, strategy=None)` | `value` combined over the network with `callback` (e.g. `set.union`) |
| `any_node(condition, *, strategy=None)` | whether `condition` holds on at least one device |
| `stabilizing_gossip(value, max_diameter, callback)` | a gossip that forgets devices farther than `max_diameter` hops, so it can adapt when values change |

Gossip functions accept a pluggable `strategy`:

- `monotonic_gossip()` (default): fast one-way gossip (`gossip_min` never forgets a
  minimum even if the device that had it leaves);
- `path_coherent_gossip(max_diameter=...)`: spatial self-stabilizing gossip based on
  loop-free `PathValue` routes;
- `time_replicated_gossip(period, max_replicas=2)`: temporal self-stabilizing gossip
  that periodically restarts overlapping replicas.

## Leader election: `phyelds.libraries.leader_election`

| Function | Returns |
| --- | --- |
| `elect_leader(area, distances=None, *, strategy=None)` | the node id of the leader elected for the device's region |
| `elect_leaders(area, distances=None, *, strategy=None)` | `True` on the devices elected as leaders, `False` otherwise |

`area` must be a finite positive bound so that candidacies of disappeared leaders can
expire and the election remains self-stabilizing. Supported strategies:

- `uuid_competition()` (default): UUID-based symmetry breaking over a gradient;
- `candidacy(strength=None)`: deterministic, priority-based bounded election (ACSOS
  2022) with loop-free path validation.

## Time & reactive state: `phyelds.libraries.time`

| Function | Returns |
| --- | --- |
| `local_time()` | the time of the device |
| `delta_time(clock=None)` | elapsed time since the previous round on this device (`0.0` on the first round) |
| `shared_clock(clock=None)` | a monotonic clock synchronized across the network, driven by the fastest device |
| `timer(duration, *, periodic=False, clock=None)` | time remaining on a countdown of length `duration` |
| `periodic_impulse(period, *, clock=None)` | `True` once every `period` time units |
| `recently_true(condition, duration, *, clock=None)` | `True` while `condition` holds and for `duration` time units afterwards |
| `time_replicated(process, period, *, max_replicas=2, clock=None)` | runs `process` in overlapping time-windowed replicas so obsolete state is periodically discarded |
| `delay(value, initial=None)` | the value `value` had in the previous round |
| `has_changed(value, *, initially=False)` | `True` on rounds where `value` differs from the previous round |
| `rising_edge(condition)`, `falling_edge(condition)` | `True` when `condition` transitions `False -> True` or `True -> False` |
| `once(value)` | `value` on the first round, `None` afterwards |
| `exponential_filter(signal, alpha)` | exponential moving average of `signal` with smoothing factor `alpha` in `[0, 1]` |
| `counter()` | how many rounds this call has run |
| `decay(value, rate)` | a value that starts at `value` and decreases by `rate` each round, down to 0 |

## Aggregate processes: `phyelds.libraries.processes`

Decorate a function with `@process` to define a spatially and temporally scoped
aggregate computation (a *bubble*), and start instances with `fn.spawn(keys, *args, **kwargs)`
(or `spawn(fn, keys, *args, **kwargs)`). Inside a `@process` function, return plain
values directly and control the bubble lifecycle either with guard functions or with
the `bubble` context manager:

| Construct | Meaning |
| --- | --- |
| `in_bubble(condition)` / `leave()` | keeps the device in the bubble when `condition` is true; otherwise exits immediately (`EXTERNAL`), discarding state and messages |
| `terminate_if(condition)` / `terminate()` | triggers a refractory termination wave that cleanly shuts down the entire bubble (`TERMINATED`) |
| `emit_if(condition)` | when `False`, the device acts as an internal relay (`BUBBLE`) without emitting its value in the returned `dict` |
| `with bubble(inside=..., terminate=..., emit=...):` | context manager combining `terminate_if`, `in_bubble`, and `emit_if` |

```python
from phyelds.calculus import aggregate
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.processes import in_bubble, process, terminate_if
from phyelds.libraries.spreading import broadcast, distance_to

@process
def alert_bubble(origin_id: int, max_hops: float = 3.0) -> int:
    is_origin = local_id() == origin_id
    dist = float(distance_to(is_origin))
    terminate_if(is_origin and sense("clear"))
    in_bubble(dist <= max_hops)
    # Only devices inside the bubble execute the lines below
    return int(broadcast(is_origin, count_nodes(dist)))

@aggregate
def program():
    new_alerts = {local_id()} if sense("smoke") else set()
    return alert_bubble.spawn(new_alerts, max_hops=3.0)
```

## Spatial & temporal logic: `phyelds.libraries.logic`

Provides **Spatial Logic for Closure Spaces (SLCS)** and **Past Computation Tree
Logic (Past-CTL)** operators from FCPP:

| Spatial (SLCS) | Returns |
| --- | --- |
| `interior(region)`, `closure(region)` | `True` on the topological interior (`all` neighbors) / closure (`any` neighbor) of `region` |
| `boundary(region)` | `closure(region) and not interior(region)` |
| `interior_boundary(region)`, `closure_boundary(region)` | the inner frontier (`region and not interior`) / outer fringe (`closure and not region`) |
| `somewhere(condition, *, max_diameter=20.0, strategy=None)` | `True` if `condition` holds on a reachable device within `max_diameter` |
| `everywhere(condition, *, max_diameter=20.0, strategy=None)` | `True` if `condition` holds on all reachable devices within `max_diameter` |
| `reaches(region, target, *, max_diameter=20.0, strategy=None)` | `True` if a path entirely inside `region` reaches a `target` device |
| `touches(region, target, *, max_diameter=20.0, strategy=None)` | `True` on devices in `region` whose connected component touches `target` |
| `surrounds(region, barrier, *, max_diameter=20.0, strategy=None)` | `True` on devices in `region` enclosed by `barrier` |

| Temporal (Past-CTL) | Returns (`scope="local" \| "all" \| "any"`) |
| --- | --- |
| `yesterday(condition, *, scope="local")` | whether `condition` held in the previous round (locally, in all neighbors, or in any neighbor) |
| `since(sustained, triggered, *, scope="local")` | whether `sustained` has held continuously since `triggered` occurred |
| `previously(condition, *, scope="local")` | whether `condition` held at least once in the past causal cone |
| `historically(condition, *, scope="local")` | whether `condition` has always held in the past causal cone |

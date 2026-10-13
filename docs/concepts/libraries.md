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
| `neighbors_distances()` | a field with the Euclidean distance to each neighbor (0 for the device itself) |
| `hops_distance()` | a field with 1 for each neighbor and 0 for the device itself |

## Spreading: `phyelds.libraries.spreading`

| Function | Returns |
| --- | --- |
| `distance_to(source, distances)` | the gradient: distance from the nearest device where `source` is true |
| `broadcast(source, data, distances)` | the `data` of the nearest source, spread along the gradient |
| `cast_from(source, data, accumulation, distances)` | like `broadcast`, applying `accumulation` at each hop |

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import broadcast

@aggregate
def leader_id():
    # every device learns the id of the nearest source
    return broadcast(sense("source"), local_id(), hops_distance())
```

## Collection: `phyelds.libraries.collect`

Collection is the dual of spreading: values flow *towards* the source along the
gradient (the `potential`), and are accumulated on the way.

| Function | Returns (at the source: over the whole network) |
| --- | --- |
| `collect_with(potential, local, accumulation)` | `local` values accumulated with `accumulation` |
| `count_nodes(potential)` | the number of devices |
| `sum_values(potential, local)` | the sum of `local` |
| `collect_or(potential, local)` | whether any device has `local` true |

```python
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.spreading import distance_to

@aggregate
def network_size():
    potential = distance_to(sense("source"), hops_distance())
    return count_nodes(potential)
```

## Gossip: `phyelds.libraries.gossip`

| Function | Returns |
| --- | --- |
| `gossip_min(value)`, `gossip_max(value)` | the minimum / maximum of `value` over the network |
| `gossip(value, callback)` | `value` combined over the network with `callback` (e.g. `set.union`) |
| `stabilizing_gossip(value, max_diameter, callback)` | a gossip that forgets devices farther than `max_diameter` hops, so it can adapt when values change |

Plain gossip only moves in one direction: `gossip_min` never forgets a minimum, even
if the device that had it leaves.

## Leader election: `phyelds.libraries.leader_election`

`elect_leaders(area, distances)` is true on the devices elected as leaders, with
roughly one leader every `area` of distance (a self-stabilising, UUID-based
symmetry breaking).

## Time: `phyelds.libraries.time`

| Function | Returns |
| --- | --- |
| `local_time()` | the time of the device |
| `counter()` | how many rounds this call has run |
| `decay(value, rate)` | a value that starts at `value` and decreases by `rate` each round, down to 0 |

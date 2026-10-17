# Standard libraries overview

`phyelds.libraries` provides a rich suite of reusable aggregate building blocks, all written in pure Python on top of [`@aggregate`](alignment.md), [`remember`](state.md), [`neighbors`](neighborhood-field.md), and [`exchange`](neighborhood-field.md#exchange). Reading their source code is one of the best ways to learn idiomatic **phyelds**.

---

## The G–C–S self-organization pattern

In aggregate computing, complex collective behaviors are rarely written from scratch with raw `remember` and `neighbors`. Instead, they are composed from three universal coordination operators—historically called **G**, **C**, and **S**:

<div class="ph-steps">
  <div class="ph-step ph-step--purple">
    <div class="ph-step-title">S — Sparse Choice</div>
    <p><code>elect_leaders()</code> breaks symmetry across the network, picking distributed coordinators separated by a target grain radius.</p>
  </div>
  <div class="ph-step ph-step--orange">
    <div class="ph-step-title">G — Spreading</div>
    <p><code>distance_to()</code> and <code>broadcast()</code> propagate distances and information outward from leaders or sources.</p>
  </div>
  <div class="ph-step">
    <div class="ph-step-title">C — Collection</div>
    <p><code>collect_with()</code> and <code>sum_values()</code> aggregate data inward along a gradient potential toward the sink.</p>
  </div>
</div>

| Operator | Module | Direction | Role |
| --- | --- | --- | --- |
| **G** (Gradient / Spreading) | [`phyelds.libraries.spreading`](../libraries/spreading-and-collect.md#spreading-phyeldslibrariesspreading) | **Outward** (source → network) | Computes distances from sources and broadcasts data or functions along shortest paths |
| **C** (Collection) | [`phyelds.libraries.collect`](../libraries/spreading-and-collect.md#collection-phyeldslibrariescollect) | **Inward** (network → sink) | Aggregates values downhill along a potential field toward one or more sinks |
| **S** (Sparse choice / Leaders) | [`phyelds.libraries.leader_election`](../libraries/self-organisation.md#leader-election-phyeldslibrariesleader_election) | **Symmetry breaking** | Elects spatially distributed leaders separated by a target grain radius |

Combining just these three blocks gives you:

- **`S → G`** (*Voronoi partitioning*): elect sparse leaders with `elect_leaders`, then `broadcast` each leader's ID so the network splits into self-healing clusters.
- **`G → C → G`** (*Regional / network-wide `summarize`*): build a gradient from a sink (`G`), collect values from all nodes into the sink (`C`), and broadcast the aggregated result back out (`G`).
- **`G + G + G`** (*`channel`*): add the gradients from a source and from a target (`G`, `G`), and compare the sum with the distance between the two, broadcast from the source (`G`): where it exceeds that distance by at most `width`, the devices form a self-healing channel along the shortest path. The [tutorial](../tutorial.md#7-composing-blocks-building-a-channel) builds a corridor with `G → C → G` instead.

---

## Explore the library guides

<div class="grid cards" markdown>

- **[Spreading, Collection & Gossip](../libraries/spreading-and-collect.md)** — Gradients (`bellman_ford`, `path_coherent`), `broadcast`, `channel`, tree/DAG collection (`point_to_point`, `multi_path`), `summarize`, and self-stabilizing gossip.
- **[Leader Election & Aggregate Processes](../libraries/self-organisation.md)** — Regional symmetry breaking (`elect_leaders`) and dynamic, spatially scoped computation bubbles (`@process` / `spawn`).
- **[Time, Reactive State & Logic](../libraries/time-and-logic.md)** — Network clocks, timers, edge detectors, filters, Spatial Logic for Closure Spaces (SLCS), and Past-CTL temporal logic.

</div>

---

## Device sensors & actuators: `phyelds.libraries.device`

Every aggregate program interacts with its host device through four basic functions in `phyelds.libraries.device`:

| Function | Returns / Effect |
| --- | --- |
| `local_id()` | The unique identifier of the current device |
| `local_position()` | The position tuple of the current device (`sense("position")`) |
| `sense(name)` | The current value of sensor `name` (`None` if missing) |
| `store(name, value)` | Writes an output named `name` for the platform/simulator to read (actuation, metrics) |

---

## Neighborhood distances: `phyelds.libraries.distances`

Spreading and leader-election functions accept a `NeighborhoodField` of distances to neighbors. When omitted, they default to `hops_distance()` (1 per hop); for physical distances in 2D, 3D, or $N$-D space, pass `neighbors_distances()`:

| Function | Returns |
| --- | --- |
| `neighbors_distances(position=None)` | A `NeighborhoodField` with the Euclidean distance to each neighbor (supports 2D, 3D, and $N$-D coordinates; defaults to `local_position()`) |
| `hops_distance()` | A `NeighborhoodField` with `1` for every neighbor and `0` for the device itself |

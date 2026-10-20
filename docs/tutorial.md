# Tutorial: from basics to self-healing fields

In this tutorial you will build your first aggregate programs step by step:

- **The gradient** (steps 1–5): every device computes its distance from the nearest *source* using only [`remember`](concepts/state.md) (time) and [`neighbors`](concepts/neighborhood-field.md) (space).
- **Self-healing** (step 6): watch the field automatically repair itself when the source moves.
- **Composing blocks** (step 7): combine spreading (`distance_to`) and collection (`collect_or`) into a self-healing corridor between two devices, a channel.

The complete runnable code for the gradient animations is in [`docs/examples/gradient.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/gradient.py).

---

## 1. Each device remembers its estimate

A device cannot know its distance from a distant source in a single round: it keeps a local estimate and refines it round after round. Local state that survives across rounds is [`remember`](concepts/state.md) (the `rep` of field calculus). Before discovering any path to a source, the estimate starts at infinity:

```python
set_distance, distance = remember(float("inf"))
```

## 2. Look at the neighbors' estimates

[`neighbors(distance)`](concepts/neighborhood-field.md) shares the device's current estimate with its immediate neighbors and returns a `NeighborhoodField`: one value per neighbor (plus the device itself). Arithmetic on fields is element-wise, so `+ 1` adds one hop to every neighbor's estimate, giving the distance *through* that neighbor:

```python
through_neighbors = neighbors(distance) + 1
```

## 3. Keep the best one

A source device is at distance `0`. Every other device picks the shortest path offered by its neighbors. Calling `exclude_self()` drops the device's own entry so that a node cannot reinforce its own outdated estimate (it returns a plain `dict`, hence `.values()`):

```python
--8<-- "gradient.py:hop_gradient"
```

Read **locally**, these five lines compare a few numbers from neighboring nodes. Read **globally**, they implement a distributed Bellman-Ford shortest-path algorithm: at every round the wave of distances expands outward from the source until the entire network converges.

![Hop-count gradient spreading along a line of four nodes](assets/hop-gradient-stages.png#only-light)
![Hop-count gradient spreading along a line of four nodes](assets/hop-gradient-stages-dark.png#only-dark)

![A hop-count gradient spreading along a line of ten devices](assets/gradient-hops.gif#only-light){ width="640" }
![A hop-count gradient spreading along a line of ten devices](assets/gradient-hops-dark.gif#only-dark){ width="640" }

!!! note "Why does the wave move more than one hop per round?"
    In the phyelds simulator, the devices scheduled at the same timestamp run one after another and read the freshest outboxes of neighbors that already ran in that step. The final converged field does not depend on execution order—only the transient speed does.

---

## 4. Run it in the simulator

Every device runs the **exact same** `@aggregate` function and reads whether it is a source from its `"source"` sensor. The [simulator](simulator.md) sets up the node positions, the neighborhood relation, and the round schedule:

```python
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.simulator import Simulator
from phyelds.simulator.deployments import grid_generation
from phyelds.simulator.neighborhood import radius_neighborhood
from phyelds.simulator.runner import schedule_program_for_all

@aggregate
def program():
    return hop_gradient(sense("source"))                                     # (1)!

simulator = Simulator()
grid_generation(simulator, width=10, height=1, spacing=1.0)                  # (2)!
simulator.environment.set_neighborhood_function(radius_neighborhood(1.1))    # (3)!
simulator.environment.add_data_for_all_nodes({"source": False})
simulator.environment.nodes[0].data["source"] = True                         # (4)!

schedule_program_for_all(simulator, start=0.0, frequency=1.0, program=program)
simulator.run(12)
print([node.data["result"] for node in simulator.environment.nodes.values()])
# [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

1. Each device reads its own `"source"` sensor (`True` on device `0`, `False` on all others) and runs `hop_gradient`.
2. Deploys 10 nodes on a line at coordinates `(0, 0), (1, 0), ..., (9, 0)`.
3. Two nodes are neighbors if their Euclidean distance is at most `1.1` (adjacent nodes on the line).
4. Marks node `0` as the source of the gradient.

---

## 5. From hops to metric distances

Counting hops ignores physical distance between devices. Replacing the constant `+ 1` with the measured Euclidean distance to each neighbor produces a **metric gradient**. That is what [`distance_to`](libraries/spreading-and-collect.md#spreading-phyeldslibrariesspreading) in `phyelds.libraries.spreading` does when paired with `neighbors_distances()`:

```python
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

@aggregate
def program():
    return distance_to(sense("source"), neighbors_distances())
```

![A distance gradient on an irregular lattice](assets/gradient-distance.gif#only-light){ width="480" }
![A distance gradient on an irregular lattice](assets/gradient-distance-dark.gif#only-dark){ width="480" }

[Run it in the playground](playground/index.md#example=gradient){ .md-button }

---

## 6. Self-healing { #6-self-healing }

Nothing in the program refers to *when* the source appeared or *where* it is located: every round recomputes the field from the current sensors and neighbor messages. When the source jumps from the bottom-left corner to the top-right corner halfway through the run, the field repairs itself with zero extra code:

![The gradient re-converging after the source moves](assets/gradient-self-healing.gif#only-light){ width="480" }
![The gradient re-converging after the source moves](assets/gradient-self-healing-dark.gif#only-dark){ width="480" }

[Move the source yourself in the playground](playground/index.md#example=gradient){ .md-button }

Look closely at the animation: the region around the *new* source settles rapidly, whereas the region around the *old* source takes longer to clear. When the old source turns off, its former neighbors still see each other's low estimates and mutually increment them little by little. This is the classic **rising-value problem** (see [Common pitfalls](pitfalls.md#expecting-instant-answers)).

!!! tip "Fast self-healing with `path_coherent`"
    When sources can disappear or move fast, pass the `path_coherent` strategy to `distance_to`:
    ```python
    from phyelds.libraries.spreading import distance_to, path_coherent

    distance_to(sense("source"), neighbors_distances(), strategy=path_coherent(max_diameter=20))
    ```
    It tracks loop-free routing paths via `exchange` so stale estimates are invalidated immediately instead of slowly counting up.

---

## 7. Composing blocks: building a channel

The real power of aggregate computing comes from **composing** field functions just like ordinary Python functions.

Suppose we want to highlight a communication corridor (a **channel**): the devices within `width` of the shortest path between a `source` device and a `target` device. We can build it in three steps by combining spreading (`distance_to`) and collection (`collect_or`):

<div class="ph-steps">
  <div class="ph-step ph-step--orange">
    <div class="ph-step-title">1. Spread (G)</div>
    <p><code>to_target = distance_to(target)</code> computes the distance from every device to the target.</p>
  </div>
  <div class="ph-step">
    <div class="ph-step-title">2. Collect (C)</div>
    <p><code>on_path = collect_or(to_target, source)</code> traces the shortest path from source downhill to target.</p>
  </div>
  <div class="ph-step ph-step--purple">
    <div class="ph-step-title">3. Dilate (G)</div>
    <p><code>distance_to(on_path) &lt; width</code> expands the 1-node path into a corridor of radius <code>width</code>.</p>
  </div>
</div>

```python
from phyelds.calculus import aggregate
from phyelds.libraries.collect import collect_or
from phyelds.libraries.device import sense
from phyelds.libraries.distances import neighbors_distances
from phyelds.libraries.spreading import distance_to

@aggregate
def my_channel(width: float = 1.6) -> float:
    distances = neighbors_distances()
    to_target = distance_to(sense("target"), distances)          # (1)!
    on_path = collect_or(to_target, sense("source"))             # (2)!
    return 1.0 if distance_to(on_path, distances) < width else 0.0  # (3)!
```

1. **Spread (`G`)**: every device computes its distance to the `target`.
2. **Collect (`C`)**: `collect_or` flows downhill along `to_target` from `source` to `target`, setting `on_path = True` on every node along the shortest path.
3. **Spread (`G`)**: a second `distance_to(on_path, ...)` measures how far each node is from the shortest path, selecting all devices within `width`.

![A self-organizing channel between bottom-left and top-right corners](assets/channel.gif#only-light){ width="480" }
![A self-organizing channel between bottom-left and top-right corners](assets/channel-dark.gif#only-dark){ width="480" }


!!! note "The library `channel` is built differently"
    `phyelds.libraries.spreading.channel(source, target, width)` needs no collection: a device belongs to it when the shortest route from the source to the target *through that device* is at most `width` longer than the shortest route overall (`to_source + to_target <= between + width`). Its `width` is a slack on the length of the path, not a distance from it: the channel is an ellipse with foci in the source and the target rather than a band, as the [3D walkthrough](walkthrough/index.md) shows step by step. The [playground](playground/index.md#example=channel) runs it with one line per term, ready to watch.

---

## Where next

- **[Core Concepts](concepts/state.md)**: dive deeper into [`remember`](concepts/state.md), [`NeighborhoodField` & `exchange`](concepts/neighborhood-field.md), [`@aggregate` alignment](concepts/alignment.md), and [Common pitfalls](pitfalls.md).
- **[Standard Libraries](concepts/libraries.md)**: explore ready-to-use blocks for spreading, collection, gossip, leader election, `@process` bubbles, time, and spatial/temporal logic.

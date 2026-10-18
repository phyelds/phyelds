# Thinking in fields: aggregate programs

Aggregate computing programs a **collective** instead of a single device. Rather than writing message handlers, socket loops, or state machines for individual nodes, you write **one function** that describes how a global distributed data structure—a **computational field**—evolves over space and time.

For the theoretical foundations, see the [main paper on aggregate computing](https://www.sciencedirect.com/science/article/pii/S235222081930032X).

---

## Local execution, global meaning

A **computational field** assigns a value to every device at every moment in time (for example: a field of temperatures, a field of distances from an exit, or a field of cluster IDs). No single coordinator holds the whole field; instead, it emerges from every device repeatedly running the same program and exchanging values only with its immediate neighbors.

![Local view of one device versus the global computational field across the network](../assets/local-vs-global.png#only-light)
![Local view of one device versus the global computational field across the network](../assets/local-vs-global-dark.png#only-dark)

Every aggregate function therefore has **two readings**:

- **Local reading**: what one device computes in a single step (for instance, *"take the minimum of my neighbors' numbers and add 1"*).
- **Global reading**: what field the entire network converges to over time (for instance, *"the shortest-path distance of every device from the nearest source"*).

You design by composing **global** fields, while Python executes the **local** steps on each device.

---

## The execution model: Sense → Compute → Act

Every device executes the aggregate program in periodic, asynchronous **rounds**. In each round, a device goes through three phases:

![The three phases of an aggregate round: Sense, Compute, and Act](../assets/round-lifecycle.png#only-light)
![The three phases of an aggregate round: Sense, Compute, and Act](../assets/round-lifecycle-dark.png#only-dark)

1. **Sense**: the runtime gathers the device's current sensor readings, the state saved at the end of its own previous round, and the most recent messages received from its current neighbors.
2. **Compute**: the device runs the `@aggregate` function from top to bottom. Whenever the code calls `remember(...)`, it reads from the previous state; whenever it calls `neighbors(...)`, it reads the neighbors' values for that exact call site and records its own value for the outbox.
3. **Act**: the runtime stores the new local state for the next round, exposes any outputs written with `store(...)` to the platform (actuators, logs, metrics), and broadcasts the single outbox packet to neighboring devices.

Rounds across different devices do **not** need to be synchronized, and devices can move, join, or leave at any time. Because every round recomputes the field from fresh inputs, aggregate programs naturally **self-heal** when the network topology changes.

---

## How space and time combine

All collective behaviors in **phyelds** come from combining just four mechanisms:

| Mechanism | Primitive | What it gives you |
| --- | --- | --- |
| **Space only** | [`neighbors(x)`](neighborhood-field.md) | 1-hop perception: compare or aggregate values across immediate neighbors |
| **Time only** | [`remember(init)`](state.md) | Local memory: counters, filters, timers, and state machines on a single node |
| **Space + Time** | `remember` + `neighbors`, or [`exchange(init)`](neighborhood-field.md#exchange) | Global propagation: information travels hop-by-hop across the whole network (gradients, broadcasts, collections, gossip) |
| **Domain splitting** | [`if` / `align`](alignment.md), [`@process`](../libraries/self-organisation.md#aggregate-processes-phyeldslibrariesprocesses) | Network partitioning: split devices into independent sub-networks that do not mix messages |

---

## The building blocks at a glance

| Construct | Field calculus | What it does |
| --- | --- | --- |
| [`@aggregate`](alignment.md) | function application | Marks a function as part of the aggregate computation and aligns its branches |
| [`remember`](state.md) | `rep` | Keeps local state that survives from one round to the next |
| [`neighbors`](neighborhood-field.md) | `nbr` | Shares a value with neighbors and returns their values as a `NeighborhoodField` |
| [`exchange`](neighborhood-field.md#exchange) | `exchange` | Evolves state and sends (possibly distinct, per-neighbor) values in one step |
| [`if` / `align`](alignment.md) | branching | Isolates branches into separate, non-interfering communication domains |
| `sense`, `store`, `local_id` | sensors / actuators | Reads device sensors and writes actuation/metric outputs ([`phyelds.libraries.device`](libraries.md#device-sensors-actuators-phyeldslibrariesdevice)) |

---

## Pragmatic and Pythonic

Most aggregate computing frameworks (such as ScaFi, Protelis, or FCPP) enforce a strictly functional style. **phyelds** is intentionally pragmatic: aggregate programs are ordinary Python functions where you can use standard loops, dictionaries, classes, and controlled mutability.

!!! tip "Three golden rules to keep in mind"
    Because Python does not enforce purity at compile time, keep these three rules in mind (see [Common pitfalls](../pitfalls.md) for concrete examples):

    1. **Decorate every aggregate helper with `@aggregate`** so its calls and `if`/`else` branches are properly aligned across devices.
    2. **Never call `neighbors` a data-dependent number of times** (e.g., inside a `for` loop whose length varies from device to device).
    3. **Keep device state in `remember`, not in Python globals or mutated neighbor objects**, because all simulated nodes share the same Python process.

---

To watch fields, neighbors and gradients evolve round by round, open the [interactive 3D walkthrough](../walkthrough/index.md), a full-screen page apart from these docs; then go on with the [tutorial](../tutorial.md).

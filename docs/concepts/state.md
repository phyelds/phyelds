# State with `remember`

A device runs the aggregate program from the top at every round, so ordinary Python local variables are lost when the round ends. `remember` keeps a value on a device from one round to the next (the `rep` construct of field calculus).

```python
from phyelds.calculus import aggregate, remember

@aggregate
def counter():
    set_count, count = remember(0)   # (1)!
    set_count(count + 1)             # (2)!
    return count                     # (3)!
```

1. On the very first round, `count` starts at the initial value `0`. On every subsequent round, `remember(0)` ignores `0` and loads the value stored at the end of the previous round.
2. `set_count(...)` updates the value to keep for the next round (and immediately updates the `count` proxy in the current round).
3. Returns `1` in round 1, `2` in round 2, `3` in round 3, and so on.

`remember(initial)` returns a pair `(update_fn, current_state)`:

1. an **update function**: call it with the value to keep for the next round;
2. the **current state**, wrapped in a `State` proxy object.

---

## How state evolves across rounds

![State evolution across three consecutive rounds using remember](../assets/state-evolution.png#only-light)
![State evolution across three consecutive rounds using remember](../assets/state-evolution-dark.png#only-dark)

---

## The `State` object

`State` is a transparent proxy: it behaves like the value it wraps, so arithmetic, comparisons, iteration, method calls, and `isinstance` all work directly on it. Use `.value` when you need the unwrapped Python object (for example, to pass it to a third-party C extension that checks exact types).

Calling the update function mutates the proxy in place too: after `set_count(count + 1)`, `count` immediately holds the new value. That is why `counter()` above returns `1` in its first round.

---

## `remember_and_evolve`

When the next value only depends on the current one, `remember_and_evolve(initial, evolution)` performs both steps and returns the updated `State`:

```python
from phyelds.calculus import aggregate, remember_and_evolve

@aggregate
def rounds_since_start():
    return remember_and_evolve(0, lambda count: count + 1)
```

---

## How state is identified

Each `remember` call is identified by **where** it is called: the chain of `@aggregate` calls that leads to it, and its position among sibling calls (see [Alignment and `@aggregate`](alignment.md)).

Because of this:

- two `remember` calls in the same function have independent states;
- calling the same `@aggregate` helper twice in a round gives each call its own independent state.

---

## How long state lives

- **State not read in a round is automatically dropped** at the end of that round. If a `remember` lives inside an `if` branch that is not taken during a round, its state is discarded; re-entering that branch in a later round restarts from `initial`. This matches the branching semantics of field calculus (see [Alignment and `@aggregate`](alignment.md)).
- **`state.forget()`** drops the state explicitly.
- **Storing `None` is equivalent to having no state**: in the next round `remember` will return its `initial` value again. Use a dedicated sentinel (such as `float("inf")` or an empty tuple `()`) if you need to represent "no value".

!!! tip "In short: rules for local state"
    - Store per-device persistent values in `remember(...)`, never in module-level Python globals.
    - If a random number should be chosen once per device (e.g., a tie-breaking UUID), wrap it in `remember(random.random())`.
    - Prefer immutable values (`tuple`, `frozenset`, frozen `dataclass`) inside `remember` so neighbors cannot accidentally mutate your state in the simulator.
    - See [Common pitfalls](../pitfalls.md) for examples.

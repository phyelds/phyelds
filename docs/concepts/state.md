# State with `remember`

A device runs the aggregate program from the top at every round, so ordinary Python local variables are lost when the round ends. `remember` keeps a local value on a device from one round to the next (the `rep` construct of field calculus).

```python
from phyelds.calculus import aggregate, remember

@aggregate
def counter():
    count, set_count = remember(0)   # (1)!
    return set_count(count + 1)      # (2)!
```

1. On the very first round, `count` starts at the initial value `0`. On every subsequent round, `remember(0)` ignores `0` and loads the value stored at the end of the previous round.
2. `set_count(...)` stores the value to keep for the next round and returns it, so `counter()` returns `1` in round 1, `2` in round 2, `3` in round 3, and so on.

`remember(initial)` returns a pair `(current_state, update_fn)`:

1. the **current state**: the plain Python value held in this round;
2. an **update function**: call it with the value to keep for the next round (it also returns that new value).

!!! note "Updating state vs. sharing state with neighbors"
    Because `count` is a plain Python value, calling `set_count(count + 1)` does **not** mutate the local variable `count` in place; rebind `count = set_count(count + 1)` or return `set_count(...)` if you need the updated value later in the round.

    When a state evolves by exchanging values with neighbors (such as in gradients, gossip, or collections), use [`exchange`](neighborhood-field.md#exchange) instead of combining `remember` and `neighbors`.

---

## How state evolves across rounds

![State evolution across three consecutive rounds using remember](../assets/state-evolution.png#only-light)
![State evolution across three consecutive rounds using remember](../assets/state-evolution-dark.png#only-dark)

---

## `remember_and_evolve`

When the next value only depends on the current one, `remember_and_evolve(initial, evolution)` performs both steps and returns the updated value:

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
- **Storing `None` is equivalent to having no state**: in the next round `remember` will return its `initial` value again. Use a dedicated sentinel (such as `float("inf")` or an empty tuple `()`) if you need to represent "no value".

!!! tip "In short: rules for local state"
    - Store per-device persistent values in `remember(...)`, never in module-level Python globals.
    - If a random number should be chosen once per device (e.g., a tie-breaking UUID), wrap it in `remember(random.random())`.
    - Prefer immutable values (`tuple`, `frozenset`, frozen `dataclass`) inside `remember` so neighbors cannot accidentally mutate your state in the simulator.
    - See [Common pitfalls](../pitfalls.md) for examples.

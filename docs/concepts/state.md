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

<div class="ph-figure">
<svg viewBox="0 0 800 135" role="img" aria-label="State evolution across three consecutive rounds using remember">
  <defs>
    <marker id="ph-st-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-magenta)" />
    </marker>
  </defs>

  <!-- Round 1 -->
  <rect x="14" y="14" width="220" height="106" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="124" y="35" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ph-diag-orange)">ROUND 1 (initial)</text>
  <text x="124" y="64" text-anchor="middle" font-size="11" class="ph-code" fill="var(--ph-diag-text)">remember(0) → 0</text>
  <text x="124" y="94" text-anchor="middle" font-size="11" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">set_count(0 + 1) → 1</text>

  <!-- Arrow 1 -> 2 -->
  <line x1="238" y1="67" x2="282" y2="67" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-st-arr)" />
  <text x="260" y="55" text-anchor="middle" font-size="9.5" fill="var(--ph-diag-muted)">saved</text>

  <!-- Round 2 -->
  <rect x="290" y="14" width="220" height="106" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="400" y="35" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ph-diag-orange)">ROUND 2</text>
  <text x="400" y="64" text-anchor="middle" font-size="11" class="ph-code" fill="var(--ph-diag-text)">remember(0) → 1</text>
  <text x="400" y="94" text-anchor="middle" font-size="11" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">set_count(1 + 1) → 2</text>

  <!-- Arrow 2 -> 3 -->
  <line x1="514" y1="67" x2="558" y2="67" stroke="var(--ph-diag-magenta)" stroke-width="2" marker-end="url(#ph-st-arr)" />
  <text x="536" y="55" text-anchor="middle" font-size="9.5" fill="var(--ph-diag-muted)">saved</text>

  <!-- Round 3 -->
  <rect x="566" y="14" width="220" height="106" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="676" y="35" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ph-diag-orange)">ROUND 3</text>
  <text x="676" y="64" text-anchor="middle" font-size="11" class="ph-code" fill="var(--ph-diag-text)">remember(0) → 2</text>
  <text x="676" y="94" text-anchor="middle" font-size="11" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">set_count(2 + 1) → 3</text>
</svg>
</div>

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

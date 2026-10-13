# State with `remember`

A device runs the program from the top at every round, so plain variables are lost
at the end of the round. `remember` keeps a value from one round to the next (the
`rep` construct of field calculus).

```python
from phyelds.calculus import aggregate, remember

@aggregate
def counter():
    set_count, count = remember(0)   # 0 the first round, then the stored value
    set_count(count + 1)
    return count                     # 1, 2, 3, ...
```

`remember(initial)` returns a pair:

1. an **update function**: call it with the value to keep for the next round;
2. the **current state**, a `State` object.

## The `State` object

`State` is a transparent proxy: it behaves like the value it wraps, so arithmetic,
comparisons, method calls and `isinstance` all work on it. Use `.value` when you
need the bare value, for example to pass it to code that does not expect a proxy.

The update function changes the proxy too: after `set_count(count + 1)`, `count`
holds the new value. That is why `counter()` above returns 1 in its first round.

## `remember_and_evolve`

When the next value only depends on the current one, `remember_and_evolve` does the
update for you and returns the new state:

```python
from phyelds.calculus import aggregate, remember_and_evolve

@aggregate
def rounds_since_start():
    return remember_and_evolve(0, lambda count: count + 1)
```

## How state is identified

Each `remember` is identified by *where* it is called: the chain of aggregate
calls that leads to it, and its position among them (see
[alignment](alignment.md)). So two `remember` calls in the same function are
independent, and the same function called twice gets two independent states.

## How long state lives

- State that the program does **not read in a round is dropped** at the end of that
  round. If a `remember` lives inside a branch that is not executed, its state is
  gone: entering the branch again starts from the initial value. This is the
  intended semantics of branching (see [alignment](alignment.md)).
- `state.forget()` drops it explicitly.
- Storing `None` is the same as having no state: in the next round `remember`
  returns its initial value again. Use another sentinel if you need "no value".

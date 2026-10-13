# Pitfalls

phyelds programs are ordinary Python, so Python will not stop you from writing
code that breaks the aggregate semantics. These are the mistakes that are easy to
make, with what goes wrong and what to do instead. Most of them are about
[alignment](concepts/alignment.md): read that page first.

## A data-dependent number of aggregate calls

Calls are aligned by their position. In a loop, the *i*-th iteration of a device is
aligned with the *i*-th iteration of its neighbors, whatever they iterate over.

```python
# ❌ device 0 iterates over ["a", "b"], the others over ["b"]:
#    device 0's "a" exchange receives the others' "b" values
@aggregate
def program():
    seen = {}
    for key in my_keys():
        seen[key] = neighbors(value_of(key))
    return seen
```

Wrapping the body in `with align(key):` does **not** fix it: the position is still
part of the path. Use one of these instead:

```python
# ✅ one exchange: share a dictionary, then pick from it
@aggregate
def program():
    mine = {key: value_of(key) for key in my_keys()}
    field = neighbors(mine)
    return {
        key: [values[key] for values in field.data.values() if key in values]
        for key in mine
    }

# ✅ the same sequence on every device
ALL_KEYS = ["a", "b"]

@aggregate
def program():
    seen = {}
    for key in ALL_KEYS:
        values = neighbors(value_of(key) if key in my_keys() else None)
        if key in my_keys():
            seen[key] = [v for v in values if v is not None]
    return seen
```

The same holds for comprehensions, `map`, and any other repetition.

## `:=` in a conditional expression does not split the network

`@aggregate` aligns the branches of a conditional expression by moving them into
lambdas. A branch with `:=` (or `yield`, `await`) would change meaning there, so
it is left as it is, and its two branches are aligned with each other: devices on
different branches exchange values.

```python
# ❌ the := keeps both branches together: robots and sensors hear each other
values = (heard := neighbors("robot")) if sense("is_robot") else neighbors("sensor")

# ✅ assign outside the expression
heard = neighbors("robot") if sense("is_robot") else neighbors("sensor")
```

## Helpers without `@aggregate`

A plain function called from an aggregate one shares its caller's alignment, and
its `if` statements are not rewritten.

```python
# ❌ the branches of `pick` are not separated
def pick(flag):
    if flag:
        return neighbors("left")
    return neighbors("right")

# ✅ decorate every function that (directly or not) calls remember or neighbors
@aggregate
def pick(flag):
    ...
```

## Aggregate functions without source code

`@aggregate` reads the source of the function to rewrite it. In code built with
`exec`, `python -c`, or the plain interactive interpreter, there is no source:
phyelds prints `WARNING: AST transformation failed` and runs the function without
the `if` rewrite (and prints it again at every call). Define aggregate functions in
a file or in a notebook cell.

## Mutating shared values

The bundled simulator delivers values by reference: the list a neighbor shared *is*
that neighbor's state. Mutating it changes another device.

```python
# ❌ appends to the neighbors' remembered lists
for other in neighbors(items.value).exclude_self().values():
    other.append(item)

# ✅ build new values
received = neighbors(items.value).exclude_self().values()
set_items(tuple({*items.value, *(x for other in received for x in other)}))
```

Prefer immutable values (tuples, frozensets, frozen dataclasses) in `remember` and
`neighbors`. Hosts written for real networks serialise messages and do not have
this problem, so code that relies on sharing works in the simulator only.

## Module-level state

Every simulated device runs in the same process, so a global variable is shared by
all of them: a hidden communication channel that does not exist on real devices.

```python
# ❌ all devices append to the same list
seen = []

@aggregate
def program():
    seen.append(local_id())

# ✅ per-device state goes in remember
@aggregate
def program():
    set_seen, seen = remember(())
    set_seen((*seen, local_id()))
```

Constants are fine; mutable globals are not.

## Random values and other per-round surprises

The program runs from the top at every round, so `random.random()` gives a new
value each round. If a device needs *one* random value (an id, a priority), keep it:

```python
_, priority = remember(random.random())   # drawn once, then remembered
```

The same applies to anything expensive or with side effects: printing, logging and
I/O run on every device at every round. To expose a value, `store` it as an output.

## Storing `None`

`None` means "no state": after `set_value(None)`, the next round `remember` returns
its initial value again. Use another sentinel (a dedicated object, `float("inf")`, an
empty tuple) for "no value yet".

## State inside branches resets

State that is not used in a round is dropped. A `remember` inside an `if` branch
starts again from its initial value every time the device re-enters the branch.
This is the intended semantics (a branch is a separate computation); if the value
must survive, `remember` it outside the `if`.

## Sharing a field

`neighbors(field)` raises `TypeError`: a `NeighborhoodField` only makes sense on the
device that built it. Share a plain value computed from it (`min(field)`,
`field.local()`, `field.exclude_self()`).

## Expecting instant answers

A field is not computed in one round: it *converges*, and the time it takes depends
on the diameter of the network. Read results after enough rounds, and design for
the transient.

Some patterns also converge more slowly in one direction. The classic gradient
lowers its estimates quickly (good news travels fast) but raises them slowly when a
source disappears, because devices keep leaning on each other's stale values (the
*rising value problem*: see the [tutorial](tutorial.md#6-self-healing)). Account for
it when a gradient drives decisions, or use a gradient that bounds it.

## Editing node data in the simulator

`node.update(new_data=...)` replaces the whole `data` dictionary, including the
state of the program. To change a sensor, assign the key:
`node.data["source"] = True`.

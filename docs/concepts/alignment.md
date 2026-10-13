# Alignment and `@aggregate`

## What alignment is

When a device calls `neighbors(x)`, it does not receive *every* value its neighbors
shared: only the values they shared **at the same point of the program**. Matching
these points across devices is called *alignment*, and it is what makes aggregate
programs composable: two independent gradients in the same program never mix their
messages.

phyelds identifies a point of the program by its **path**: the chain of aggregate
calls that lead to it, each with its position among its siblings. For example:

```python
@aggregate
def program():
    a = neighbors(1)        # path: program@0 / neighbors@0
    b = neighbors(2)        # path: program@0 / neighbors@1
    return gradient(...)    # path: program@0 / gradient@2 / ...
```

The same path also identifies the state of [`remember`](state.md).

## What `@aggregate` does

`@aggregate` marks a function as part of the aggregate computation. When it runs,
it:

1. **pushes the function on the path**, so everything it calls is aligned under it;
2. **rewrites every `if` statement** so that its two branches are aligned under
   different names (`align_left` / `align_right`). Devices that take different
   branches therefore do not see each other's values, and the state of a branch
   that is not taken is dropped: the branches behave as separate, non-communicating
   parts of the network.

```python
@aggregate
def program():
    if sense("is_robot"):
        return neighbors("robot")      # robots only hear robots
    else:
        return neighbors("sensor")     # sensors only hear sensors
```

!!! warning
    Only `if` **statements** in `@aggregate` functions are rewritten. A conditional
    *expression* (`a if c else b`), or an `if` in a helper function without
    `@aggregate`, does not split the network. See [pitfalls](../pitfalls.md).

To see how a function is rewritten, use `str_transformed_code`, or set the
environment variable `PHYELDS_DEBUG_AST=1` to print every transformed function:

```python
from phyelds.calculus import str_transformed_code
print(str_transformed_code(program))
```

The rewrite needs the source code of the function, so aggregate functions must be
defined in a file or a notebook cell. If the source is not available (e.g. code
built with `exec`), phyelds prints a warning and runs the function as is.

## Explicit alignment with `align`

`align(name)` opens an aligned block by hand: values shared inside it are only seen
by devices that entered a block with the same name *at the same position*.

```python
from phyelds.calculus import aggregate, align, neighbors

@aggregate
def per_team(team: str):
    with align(team):
        return sum(neighbors(1))   # size of my team's neighborhood
```

Because the position is part of the path, `align` does **not** make a loop safe if
devices iterate over different sequences; see
[pitfalls](../pitfalls.md#a-data-dependent-number-of-aggregate-calls) for the
patterns that work.

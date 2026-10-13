# Aggregate programs

Aggregate computing programs a *collective* instead of a single device. The main
abstraction is the **computational field**: a value spread over space and time,
one value per device at each moment. A field cannot be read or written from a
single place; it emerges from every device running the same program and talking
only to its neighbors.

For the theory, see the
[main paper on aggregate computing](https://www.sciencedirect.com/science/article/pii/S235222081930032X).

## The execution model

Every device repeats *rounds*. In each round a device:

1. **senses**: reads its sensors (position, time, anything the platform provides),
   the messages its neighbors sent in their last round, and the state it kept
   from its own previous round;
2. **computes**: runs the whole aggregate program, from the top;
3. **acts**: sends the values the program shared with `neighbors(...)`, keeps the
   state written with `remember(...)`, and exposes the outputs written with
   `store(...)`.

Rounds of different devices are not synchronised, and neighbors may change between
rounds. Aggregate programs are written to tolerate this: they *converge* to the
right field, and *re-converge* when the network changes.

## Local and global reading

The same code has two readings:

- **local**: what one device does in one round (compare a few numbers);
- **global**: what field the whole system computes over time (a distance map, a
  leader, a sum over the network).

You design with the global reading in mind and write the local one. The
[tutorial](../tutorial.md) shows both on the gradient.

## The building blocks

| Construct | Field calculus | What it does |
| --- | --- | --- |
| [`@aggregate`](alignment.md) | function call | marks code that takes part in the aggregate computation |
| [`remember`](state.md) | `rep` | state that survives across rounds |
| [`neighbors`](neighborhood-field.md) | `nbr` | share a value and get the neighbors' ones |
| [`if` / `align`](alignment.md) | branching | split the network into parts that do not interfere |
| `sense`, `store`, `local_id` | sensors / actuators | talk to the device (`phyelds.libraries.device`) |

## phyelds and the functional style

Most incarnations of aggregate computing are purely functional. phyelds is more
pragmatic: programs are ordinary Python functions, with loops, dictionaries,
lambdas and some controlled mutability. The price is that a few rules matter more,
because Python does not enforce them: the [pitfalls](../pitfalls.md) page lists them.

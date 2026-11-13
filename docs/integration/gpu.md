# GPU (PyTorch)

The `phyelds-gpu` package runs phyelds programs on many devices at once, as tensors with a
row per device, on a CPU or on a GPU: the same `@aggregate` programs and the same standard
libraries, without changes.

```bash
pip install phyelds-gpu
```

It installs a compatible phyelds release and PyTorch; for a GPU, install the build of
PyTorch for it first, as [pytorch.org](https://pytorch.org/get-started/locally/) explains.

---

## How it works

phyelds writes the calculus once, on the operations of an engine
(`phyelds.vm.Engine`): reading and writing the state, sending, gathering what the
neighbors sent, choosing a branch. A `MutableEngine` runs them for one device;
`phyelds.gpu.BatchEngine` runs them for a batch of devices, with tensors:

- **Values**: each value of the program holds a row per device. A sensor is a tensor with
  a row per device, or one value for all of them.
- **Neighborhoods**: `neighbors` and `exchange` give a `BatchField`: a value of each
  device, and one on each edge into it. It has the operations of `NeighborhoodField`, run
  for all the devices together.
- **Branches**: `@aggregate` rewrites the `if` statements, the conditional expressions,
  `and`, `or`, `not`, `min` and `max` for a batch engine. Each side runs for the devices
  taking it, with the alignment it has on a device of its own, and the values merge after
  it.
- **The graph**: `radius_topology(positions, radius)` links the devices within `radius`,
  through a uniform grid on the tensors; `GraphTopology.from_neighbors` takes a mapping of
  neighbors instead.

The results, round by round, are those of the same program on each device on its own: the
tests of the package check it against `SynchronousRuntime`, `AsynchronousRuntime` and the
wavefront runtime of phyelds.

---

## Synchronous rounds

`BatchSynchronousRuntime` runs a program on every device at once, one synchronous round at
a time: in a round, each device reads what its neighbors sent in the previous one, as
[`SynchronousRuntime`](index.md#parallel-rounds) does.

```python
--8<-- "gpu.py:program"
```

```python
--8<-- "gpu.py:world"
```

```python
--8<-- "gpu.py:synchronous"
```

Each result has a row per device: `distances[i]` is the distance of device `i`, and
`counts[0]` the number of devices that reach the source, counted at the source.

---

## Wavefronts

`BatchWavefrontRuntime` gives each device a clock of its own, and the messages a channel
with delays and losses, as the [wavefront simulation](../reference/experimental.md#phyelds.experimental.wavefront)
of `phyelds.experimental` does, with the same `Clock` and `Channel` objects: it runs
together, in a wavefront, the devices that do not depend on each other.

```python
--8<-- "gpu.py:wavefronts"
```

With no delay, the results are those of running the rounds one at a time in time order;
with a delay, or a `window`, more devices run together, up to every device on aligned
clocks. The whole example is
[`docs/examples/gpu.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/gpu.py).

---

## What a program can do on a batch

Most programs run unchanged. A batch engine adds a few rules, all checked at run time:

- **Branches inside loops, `with` and `try`** stay plain Python: their conditions need a
  single truth value, the same for every device. A condition with a value per device
  there raises `TypeError`.
- **Callbacks of fields compute elementwise**: `map`, `any` or `count_matching` get
  tensors with a row per entry. Pass the values of the device as arguments of `map`, not
  in a closure: `parents.map(operator.eq, local_id())`, not
  `parents.map(lambda parent: parent == my_id)`.
- **Folds** take `operator.add`, `operator.mul`, `max`, `min`, and, on booleans,
  `operator.or_` and `operator.and_`; any other function raises `TypeError`.
- **`None` is NaN**: a device for which a branch returns nothing gets NaN, which, as
  `None`, equals nothing.
- **A variable left as different functions** by the branches of an `if` cannot be used
  after it: using it raises `TypeError`.

Not supported yet: sending a field to address each neighbor its own value (anisotropic
`exchange`), metric distances (`neighbors_distances`, which compares positions with
`math.dist`), and devices joining or leaving.

---

## Performance

A gradient, a gossip and a count, in synchronous rounds on a CPU (an Intel Core i9-14900KF),
about 8 neighbors per device:

| Devices | phyelds `SynchronousRuntime` | `BatchSynchronousRuntime` |
|---:|---:|---:|
| 1,000 | 20,600 device-rounds/s | 270,000 device-rounds/s |
| 10,000 | 20,000 device-rounds/s | 1,430,000 device-rounds/s |
| 100,000 | | 3,270,000 device-rounds/s |

In wavefronts each step still scans every device and every edge, whatever the size of the
wavefront: faster steps for small wavefronts are on the way.

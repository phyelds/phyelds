---
draft: true
---

# Optional C Engine (`phyelds-accel`)

`phyelds-accel` is an optional package that replaces the per-device Python `MutableEngine` and round loop with a small CPython C extension (`phyelds.accel._engine`), while running **the exact same `@aggregate` Python programs unchanged**.

```bash
pip install phyelds-accel
```

The package ships its C source (`native/engine.c`) and compiles it once against the running CPython interpreter (3.12–3.14, including free-threaded 3.14t) using the system C compiler (`cc`, `gcc`, or `clang`), caching the resulting shared object automatically. The core `phyelds` package remains pure Python with zero dependencies.

---

## Usage

Swap `phyelds.vm.synchronous.SynchronousRuntime`, `phyelds.vm.asynchronous.AsynchronousRuntime`, or `phyelds.vm.rounds.run_round` for their `phyelds.accel` counterparts:

```python
from phyelds.accel import AsynchronousRuntime, SynchronousRuntime, run_round

runtime = SynchronousRuntime(program)
for step in range(steps):
    results = runtime.run_round(sensors, neighbors)
```

No `@aggregate` function, library call, custom Python object, `NeighborhoodField`, or sensor/actuator changes.

---

## How it works

1. **Flat C alignment stack & pointer-keyed segment cache**: `NativeEngine` keeps the alignment stack in fixed inline C arrays (`uint32_t stack_codes[128]`, `PyObject *stack_keys[128]`, `uint32_t count_stack[128]`, growing dynamically only if needed) and caches `(parent, name, counter) -> 30-bit compact key` per engine instance with pre-hashed `PyLongObject` keys.
2. **Bit-for-bit wire compatibility**: `NativeEngine` computes the exact 30-bit polynomial hash of `CompactPaths`, so its outboxes and snapshots interoperate directly with `MutableEngine(paths="compact")` and `Device(..., paths="compact")` on MicroPython, ARGoS, and Webots.
3. **Zero-allocation device transitions in `run_chunk`**: for synchronous rounds, `run_chunk` sets the `engine` `ContextVar` once per chunk, reuses a single `NativeNodeContext` and scratch inbox dictionary across all devices in the chunk, and allocates an `outputs` dictionary only when a device calls `store(...)`.
4. **Free-threaded Python (`Py_MOD_GIL_NOT_USED`)**: the extension declares PEP 703 free-threading support and keeps all mutable engine caches per-instance (thread-local in `SynchronousRuntime`), so importing `phyelds.accel` keeps the GIL disabled on Python 3.14t.

---

## Cost vs. benefit

### Speed-up on `SynchronousRuntime` (5,000–10,000 nodes, `degree=8`, single core)

| Stage | `master` Python VM (agent-rounds/s) | Pure-Python fast paths | `phyelds-accel` C engine | `accel` vs. `master` |
|---|---|---|---|---|
| `empty` | 217,170 | 755,068 | 2,422,088 | **11.2x** |
| `gradient` (`distance_to`) | 40,795 | 65,337 | 80,919–90,849 | **2.0–2.4x** |
| `gossip` (`gossip_max`) | 59,436 | 87,350 | 131,157 | **2.2x** |
| `count` (`count_nodes`) | 17,633 | 24,862 | 39,118 | **2.2x** |

### Why per-device execution stops at ~80k–130k agent-rounds/s

- `NativeEngine` reduces engine + round-loop bookkeeping to **~0.4 µs per device-round** (`2.4M` empty agent-rounds/s).
- The remaining **7–11 µs per device-round** is spent inside CPython executing the `@aggregate` bytecode frames themselves (`distance_to`, `hops_distance`, `neighbors`, `exchange`, lambda closures, and `NeighborhoodField` dictionary operations).
- Because arbitrary Python values (`set`, tuples, dataclasses, closures) live as `PyObject*` references, any engine that runs arbitrary per-device `@aggregate` Python functions once per node is bounded by ~100k–200k agent-rounds/s per core. Reaching `10M+` agent-rounds/s requires executing field operations over whole-network arrays/tensors (SPMD) rather than calling Python frames once per node.

### Engineering & maintenance cost

- **Footprint**: ~690 lines of C (`native/engine.c`, CPython `<Python.h>` only, no third-party C/Rust dependencies) and ~250 lines of Python (`build.py`, `runtime.py`).
- **Portability**: requires a host C compiler (`cc`/`gcc`/`clang`) and Python headers (`Python.h`) at first import or build time unless pre-built wheels (`cibuildwheel`) are distributed.

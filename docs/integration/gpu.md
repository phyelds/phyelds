---
draft: true
---

# Concurrent-Batch GPU Execution (`phyelds-gpu`)

`phyelds-gpu` executes **unmodified `@aggregate` Python programs** on PyTorch tensors (CPU SIMD, NVIDIA CUDA, or Apple MPS) in **concurrent wavefront batches**, spanning decentralized asynchronous discrete-event simulations (DES) and full-system synchronous rounds under a single runtime contract.

```bash
pip install phyelds-gpu
```

---

## One program, any schedule

Write standard `@aggregate` functions using ordinary Python `if / else` statements, conditional expressions (`a if c else b`), `sense`, `store`, `neighbors`, `remember`, `exchange`, and the standard libraries (`distance_to`, `neighbors_distances`, `gossip_max`, `gossip_min`, `gossip_mean`, `count_nodes`, `sum_values`, `mean_values`, `collect_or`, `shared_clock`, `timer`, `rising_edge`, ...):

```python
import torch
from phyelds.calculus import aggregate
from phyelds.gpu import GpuWavefrontRuntime
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import local_id, sense
from phyelds.libraries.gossip import gossip_max
from phyelds.libraries.spreading import distance_to
from phyelds.vm.wavefront import Channel, WeibullClock


@aggregate
def swarm_telemetry():
    potential = distance_to(sense("source"))
    return potential, gossip_max(local_id()), count_nodes(potential)


positions = torch.rand((100_000, 2), dtype=torch.float64, device="cuda") * 200.0
sensors = {"source": torch.arange(100_000, device="cuda") == 0}

simulator = GpuWavefrontRuntime(
    swarm_telemetry,
    positions=positions,
    radius=1.6,
    clock=WeibullClock(period=1.0, shape=4.0, random_phase=True),
    channel=Channel(delay=0.05, loss=0.02, retention=2.5),
    device="cuda",
)
simulator.run_until(10.0, sensors)
potentials, leaders, counts = simulator.results_tensor()
```

---

## How concurrent-batch wavefronts work

Each node $i \in \{0, \dots, N-1\}$ holds its own wakeup clock `next_time[i]` (with independent random phase, clock drift, or Weibull/Exponential intervals), and each directed link $(u \to v)$ carries a two-slot `(committed, pending)` radio buffer in VRAM with propagation latency `delay`, `jitter`, packet `loss`, and `retention` expiry.

At every step, `select_wavefront()` runs on the GPU and selects all nodes within the lookahead horizon that have **no causally preceding neighbor**:

$$\text{blocked}(u \to v) \iff t_u + \tau_{\text{eff}} < t_v \;\lor\; (\tau_{\text{eff}} = 0 \land t_u = t_v \land u < v)$$

where $\tau_{\text{eff}} = \max(\text{channel.delay}, \text{window})$.

1. **Exact conservative DES (`delay = 0, window = 0`)**: every local temporal minimum on the graph executes concurrently (`~6–10%` of all nodes per GPU pass at degree 8), producing **exact round-by-round equivalence** with single-event sequential spikes (`AsynchronousRuntime`).
2. **Realistic decentralized radio (`delay > 0`, `loss > 0`, `retention`)**: neighbors firing within the radio propagation/airtime latency cannot receive each other's in-flight packet anyway, so they execute concurrently in larger GPU batches (`~10–25%` of the network per pass), enqueue in-flight messages arriving at $t_u + \text{delay} + \text{jitter}$, and advance.
3. **Worst-case synchronous limit (`PeriodicClock(random_phase=False)` with `delay > 0` or `window > 0`)**: `blocked` is `False` on every edge, so **every batch spans 100% of the network ($B = V$)**, matching `SynchronousRuntime` (`GpuSynchronousRuntime` provides a dedicated convenience wrapper).

---

## Supported calculus subset

Because device states and messages live in contiguous GPU tensors, `phyelds-gpu` supports programs whose values are numeric/boolean scalars or fixed-dimension coordinate vectors:

- **Supported unchanged**: `@aggregate`, `neighbors`, `remember`, `remember_and_evolve`, `exchange`, `if / elif / else` statements, `a if c else b`, `not` / `and` / `or`, `sense`, `store`, `local_id`, `local_position`, `local_time`, `hops_distance`, `neighbors_distances`, `distance_to` (Bellman-Ford), `gossip_max`, `gossip_min`, `gossip_mean`, `any_node`, `find_parent`, `count_nodes`, `sum_values`, `mean_values`, `collect_or`, `counter`, `decay`, `delay`, `delta_time`, `shared_clock`, `timer`, `rising_edge`, `falling_edge`, `exponential_filter`.
- **Not supported on GPU tensors** (require Python per-device runtimes): variable-length path tuples (`path_coherent`, `candidacy`), dynamic Python sets/dicts (`stabilizing_gossip`, `spawn` / `@process`), and custom non-associative Python object reducers.

---

## Benchmarks (NVIDIA GeForce RTX 4070, `degree = 8`)

### Synchronous rounds (`B = V`, unchanged `benchmarks/programs.py`)

| Nodes | Grid build (`radius_topology`) | `gradient` (agent-rounds/s) | `gossip` (agent-rounds/s) | `count` (agent-rounds/s) |
|---:|---:|---:|---:|---:|
| 10,000 | 1.2 ms | 9.66M | 16.09M | 4.43M |
| 100,000 | 14.1 ms | 11.64M | 18.15M | 9.94M |
| 500,000 | 17.1 ms | 94.99M (`5.3 ms`/round) | 170.48M (`2.9 ms`/round) | 35.26M (`14.2 ms`/round) |
| 1,000,000 | 39.5 ms | 89.53M (`11.2 ms`/round) | **174.37M (`5.7 ms`/round)** | **35.36M (`28.3 ms`/round)** |

### Decentralized asynchronous wavefronts (`WeibullClock(1.0, shape=4.0)` + `loss=2%`, `retention=2.5s`, `gradient`)

| Nodes | Mode | Mean concurrent batch $\|B\|$ | Throughput (agent-rounds/s) |
|---:|---|---:|---:|
| 100,000 | Exact DES (`delay=0`) | 6,498 (`6.5%`) | 3.86M |
| 100,000 | Radio (`delay=50ms`) | 10,083 (`10.1%`) | 4.85M |
| 100,000 | Relaxed (`window=200ms`) | 22,260 (`22.3%`) | 12.19M |
| 500,000 | Exact DES (`delay=0`) | 31,084 (`6.2%`) | 9.93M |
| 500,000 | Radio (`delay=50ms`) | 50,377 (`10.1%`) | 13.80M |
| 500,000 | Relaxed (`window=200ms`) | 108,546 (`21.7%`) | **24.61M** |

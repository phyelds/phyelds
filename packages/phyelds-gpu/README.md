# phyelds-gpu

PyTorch backend for [phyelds](https://github.com/phyelds/phyelds): the devices of an aggregate
system as tensors, on CPU or GPU.

Work in progress, not released yet. `BatchSynchronousRuntime` runs an unmodified `@aggregate`
program on every device at once, one synchronous round at a time, with the results of
phyelds' own `SynchronousRuntime`:

```python
import torch
from phyelds.calculus import aggregate
from phyelds.libraries.device import sense
from phyelds.libraries.spreading import distance_to
from phyelds.gpu import BatchSynchronousRuntime, radius_topology

@aggregate
def gradient():
    return distance_to(sense("source"))

positions = torch.rand(100_000, 2, dtype=torch.float64) * 200
runtime = BatchSynchronousRuntime(gradient, radius_topology(positions, 1.0))
distances = runtime.run_round({"source": torch.arange(100_000) == 0})  # one per device
```

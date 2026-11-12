"""
The PyTorch backend of phyelds: a gradient, and a count of the devices that reach the source,
on 2,000 devices at once, in synchronous rounds and in wavefronts over a radio channel.

Run it from the root of the repository, with PyTorch installed:

    PYTHONPATH="packages/phyelds-gpu/src" poetry run python docs/examples/gpu.py
"""
import torch

from phyelds.calculus import aggregate
from phyelds.experimental.wavefront import Channel, WeibullClock
from phyelds.gpu import BatchSynchronousRuntime, BatchWavefrontRuntime, radius_topology
from phyelds.libraries.collect import count_nodes
from phyelds.libraries.device import sense
from phyelds.libraries.spreading import distance_to


# --8<-- [start:program]
@aggregate
def gradient():
    potential = distance_to(sense("source"))
    return potential, count_nodes(potential)
# --8<-- [end:program]


# --8<-- [start:world]
def world(count: int, device: str = "cpu"):
    """A random cloud of ``count`` devices with about 8 neighbors each, the first a source."""
    side = (count / 2.5) ** 0.5
    positions = torch.rand(count, 2, dtype=torch.float64, device=device) * side
    topology = radius_topology(positions, 1.0)
    sensors = {"source": torch.arange(count, device=device) == 0}
    return topology, sensors
# --8<-- [end:world]


# --8<-- [start:synchronous]
def synchronous(topology, sensors, rounds: int):
    """The distances and the counts after ``rounds`` synchronous rounds of every device."""
    runtime = BatchSynchronousRuntime(gradient, topology)
    for _ in range(rounds):
        distances, counts = runtime.run_round(sensors)  # a row per device
    return distances, counts
# --8<-- [end:synchronous]


# --8<-- [start:wavefronts]
def wavefronts(topology, sensors, until: float):
    """The latest distance of each device after wavefronts until ``until``."""
    runtime = BatchWavefrontRuntime(
        gradient,
        topology,
        clock=WeibullClock(period=1.0, shape=4.0),
        channel=Channel(delay=0.05, loss=0.02),
        seed=1,
    )
    (distances, held), _ = runtime.run_until(until, sensors)  # the latest results, and who ran
    return distances, held
# --8<-- [end:wavefronts]


def main() -> None:
    """Run both on 2,000 devices, on the GPU if there is one, until the count settles."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    topology, sensors = world(2_000, device)
    distances, counts = synchronous(topology, sensors, rounds=120)
    reached = int(torch.isfinite(distances).sum())
    print(f"synchronous: {reached} devices reach the source, which counts {int(counts[0])}")
    distances, _ = wavefronts(topology, sensors, until=120.0)
    print(f"wavefronts: {int(torch.isfinite(distances).sum())} devices reach the source")


if __name__ == "__main__":
    main()

"""
PyTorch backend of phyelds: the devices of an aggregate system as tensors, on CPU or GPU.

``BatchSynchronousRuntime`` runs an unmodified ``@aggregate`` program on every device at once,
one synchronous round at a time: ``BatchEngine`` implements the operations of the engine of
phyelds on tensors with a row per device, and ``BatchField`` the neighborhood field. The graph
comes from a radius search on a uniform grid (``radius_topology``) or from a mapping of
neighbors (``GraphTopology.from_neighbors``).
"""
from phyelds.gpu.engine import BatchEngine
from phyelds.gpu.fields import BatchField
from phyelds.gpu.runtime import BatchSynchronousRuntime
from phyelds.gpu.topology import BatchEdges, GraphTopology, radius_topology
from phyelds.gpu.wavefront import BatchWavefrontRuntime, BatchWavefrontStep, select_batch

__all__ = [
    "BatchEdges",
    "BatchEngine",
    "BatchField",
    "BatchSynchronousRuntime",
    "BatchWavefrontRuntime",
    "BatchWavefrontStep",
    "GraphTopology",
    "radius_topology",
    "select_batch",
]

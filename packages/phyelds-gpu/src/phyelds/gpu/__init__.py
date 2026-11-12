"""
PyTorch backend of phyelds: the devices of an aggregate system as tensors, on CPU or GPU.

For now it builds the communication graph of many devices with a radius search on a uniform
grid (``radius_topology``), gathers the edges into a batch of them (``GraphTopology.batch``),
and holds the neighborhood field of a batch (``BatchField``).
"""
from phyelds.gpu.fields import BatchField
from phyelds.gpu.topology import BatchEdges, GraphTopology, radius_topology

__all__ = ["BatchEdges", "BatchField", "GraphTopology", "radius_topology"]

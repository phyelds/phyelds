# phyelds-gpu

PyTorch backend for [phyelds](https://github.com/phyelds/phyelds): the devices of an aggregate
system as tensors, on CPU or GPU.

Work in progress, not released yet. For now it builds the communication graph of many devices
with a radius search on a uniform grid (`radius_topology`), and gathers the edges into a batch
of them (`GraphTopology.batch`).

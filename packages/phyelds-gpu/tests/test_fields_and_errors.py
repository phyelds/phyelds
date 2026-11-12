"""Unit tests for BatchedNeighborhoodField algebra, reductions, and validation errors."""

import operator

import pytest
import torch

from phyelds.calculus import aggregate, neighbors
from phyelds.gpu import (
    BatchedNeighborhoodField,
    GpuSynchronousRuntime,
    GpuWavefrontRuntime,
    GraphTopology,
)
from phyelds.libraries.device import local_id, sense, store
from phyelds.vm.wavefront import PeriodicClock

DEVICES = ["cpu", "cuda"] if torch.cuda.is_available() else ["cpu"]


def _sample_fields(device: str) -> tuple[BatchedNeighborhoodField, BatchedNeighborhoodField]:
    topo = GraphTopology.from_neighbors({0: [1, 2], 1: [0], 2: [0]}, device=device)
    edges = topo.full_batch()
    local_a = torch.tensor([2, 4, 6], dtype=torch.int64, device=device)
    edge_a = local_a[edges.global_sender]
    valid = torch.tensor([True, True, True, False], dtype=torch.bool, device=device)
    local_b = torch.tensor([1, 2, 3], dtype=torch.int64, device=device)
    edge_b = local_b[edges.global_sender]
    return (
        BatchedNeighborhoodField(edges, local_a, edge_a, valid),
        BatchedNeighborhoodField(edges, local_b, edge_b, valid),
    )


@pytest.mark.parametrize("device", DEVICES)
def test_batched_field_arithmetic_bitwise_and_comparison_operators(device: str):
    fa, fb = _sample_fields(device)

    assert (fa + fb).local() is not None
    assert (1 + fa).local_val.tolist() == [3, 5, 7]
    assert (fa - fb).local_val.tolist() == [1, 2, 3]
    assert (fa * 2).local_val.tolist() == [4, 8, 12]
    assert (fa / 2).local_val.tolist() == [1.0, 2.0, 3.0]
    assert (fa // fb).local_val.tolist() == [2, 2, 2]
    assert (fa % 3).local_val.tolist() == [2, 1, 0]
    assert (fb ** 2).local_val.tolist() == [1, 4, 9]
    assert (fa & fb).local_val.tolist() == [0, 0, 2]
    assert (fa | fb).local_val.tolist() == [3, 6, 7]
    assert (fa ^ fb).local_val.tolist() == [3, 6, 5]
    assert (~fb).local_val.tolist() == [-2, -3, -4]
    assert (fb < fa).all().tolist() == [True, True, True]
    assert (fb <= fa).any().tolist() == [True, True, True]
    assert (fa > fb).none().tolist() == [False, False, False]
    assert (fa >= 4).count_matching(lambda t: t).tolist() == [2, 1, 1]


@pytest.mark.parametrize("device", DEVICES)
def test_batched_field_reductions_folds_and_validation(device: str):
    fa, _ = _sample_fields(device)
    assert fa.without_self().local() is None
    assert fa.product(start=2).tolist() == [96, 16, 12]
    assert fa.id_of_max().tolist() == [2, 1, 2]
    assert fa.coerce_in(3, 5).local_val.tolist() == [3, 4, 5]
    assert fa.replace_matching(0, lambda t: t > 4).local_val.tolist() == [2, 4, 0]

    assert fa.fold(1, operator.mul).tolist() == [48, 8, 6]
    assert fa.fold(0, max).tolist() == [6, 4, 6]
    assert fa.fold(99, min).tolist() == [2, 2, 6]
    assert fa.fold(True, lambda a, b: a and b).dtype == torch.bool

    with pytest.raises(ValueError, match="lower bound"):
        fa.coerce_in(5, 1)
    with pytest.raises(NotImplementedError):
        fa.min(key=lambda x: x)
    with pytest.raises(NotImplementedError):
        fa.max(key=lambda x: x)
    with pytest.raises(NotImplementedError):
        fa.id_of_min(key=lambda _i, x: x)
    with pytest.raises(NotImplementedError):
        fa.id_of_max(key=lambda _i, x: x)
    with pytest.raises(TypeError, match="fold requires"):
        fa.fold(0, lambda a, b: (a, b))
    with pytest.raises(TypeError, match="max and min"):
        fa._reduce_all(0, lambda *xs: xs)  # pylint: disable=protected-access


def test_gpu_runtimes_validate_inputs_and_handle_edge_cases():
    @aggregate
    def nested_field_error():
        return neighbors(neighbors(1))

    rt = GpuSynchronousRuntime(nested_field_error)
    assert rt.run_round({}, {}) == {}
    with pytest.raises(TypeError, match="Neighborhood is not supported"):
        rt.run_round({0: {}}, {0: []})

    @aggregate
    def assign_in_branches():
        val = 0
        if sense("on"):
            val = int(local_id()) + 10
            store("tag", val)
        else:
            val = 1 if False else 2
        if not sense("on") or sense("extra"):
            val = val + 1
        return val

    branch_rt = GpuSynchronousRuntime(assign_in_branches)
    out = branch_rt.run_round(
        {0: {"on": True, "extra": False}, 1: {"on": False, "extra": True}},
        {0: [1], 1: [0]},
    )
    assert out == {0: 10, 1: 3}
    assert branch_rt.outputs == {0: {"tag": 10}, 1: {}}
    branch_rt.reset()
    assert branch_rt.outputs == {}

    with pytest.raises(ValueError, match="topology="):
        GpuWavefrontRuntime(assign_in_branches)
    with pytest.raises(ValueError, match="non-negative"):
        GpuWavefrontRuntime(
            assign_in_branches,
            topology=GraphTopology.from_neighbors({0: []}),
            window=-1.0,
        )

    empty_wf = GpuWavefrontRuntime(
        assign_in_branches,
        topology=GraphTopology.from_neighbors({}),
        clock=PeriodicClock(1.0),
    )
    assert empty_wf.earliest_time() == float("inf")
    assert empty_wf.step({}).devices == ()
    assert empty_wf.results_tensor() is None

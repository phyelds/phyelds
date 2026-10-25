"""Keep the documented ARGoS program working without requiring the simulator."""
import importlib.util
from pathlib import Path

from phyelds.vm.device import Device

EXAMPLE = Path(__file__).resolve().parents[3] / "docs/examples/argos/gradient.py"


def test_argos_example_computes_metric_distances_without_gps():
    spec = importlib.util.spec_from_file_location("argos_gradient", EXAMPLE)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    devices = [Device(node_id, example.main) for node_id in range(5)]
    for _ in range(12):
        payloads = []
        for node_id, device in enumerate(devices):
            peers = [other for other in (node_id - 1, node_id + 1) if 0 <= other < 5]
            payloads.append(device.run_round({
                "source": node_id == 0, "neighbors_distances": {peer: 0.5 for peer in peers},
            }))
        for node_id, payload in enumerate(payloads):
            for peer in (node_id - 1, node_id + 1):
                if 0 <= peer < 5:
                    devices[peer].receive(node_id, payload)
    assert [device.result for device in devices] == [0, 0.5, 1, 1.5, 2]

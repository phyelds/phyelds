"""Keeps the integration example of the docs working."""
import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "custom_runtime.py"


def _load_example():
    spec = importlib.util.spec_from_file_location("custom_runtime_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


custom_runtime = _load_example()


def test_custom_runtime_computes_a_gradient_on_a_line():
    devices = custom_runtime.line_of_devices(size=4, source=0)
    links = custom_runtime.line_links(size=4)

    results = custom_runtime.run_rounds(devices, links, custom_runtime.gradient, rounds=6)

    assert results == {0: 0, 1: 1, 2: 2, 3: 3}


def test_custom_runtime_exposes_the_outputs_stored_by_the_program():
    devices = custom_runtime.line_of_devices(size=3, source=2)
    links = custom_runtime.line_links(size=3)

    custom_runtime.run_rounds(devices, links, custom_runtime.gradient, rounds=5)

    assert [device.outputs["is_far"] for device in devices.values()] == [True, False, False]


def test_custom_runtime_messages_are_copies():
    devices = custom_runtime.line_of_devices(size=2, source=0)
    links = custom_runtime.line_links(size=2)
    custom_runtime.run_rounds(devices, links, custom_runtime.gradient, rounds=1)

    inbox = custom_runtime.collect_inbox(devices, links, device_id=1)

    assert inbox[0] == devices[0].outbox
    assert inbox[0] is not devices[0].outbox

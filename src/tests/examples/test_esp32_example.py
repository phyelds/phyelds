"""Keeps the ESP32 example of the docs working, on CPython and on MicroPython."""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from phyelds.micropython.build import build

EXAMPLE = Path(__file__).resolve().parents[3] / "docs" / "examples" / "esp32" / "main.py"
MICROPYTHON = shutil.which("micropython")
# ponytail: about 2x the heap an ESP32 needs, as objects are twice as large on the 64-bit
# unix port; confirm on a board
HEAP = "160k"
LINE = """
import json
import main

ids = (64, 1000, 17)
devices = [main.Device(device_id) for device_id in ids]
for _ in range(6):
    for index, device in enumerate(devices):
        payload, outputs = device.run_round({"source": index == 0})
        for other in (index - 1, index + 1):
            if 0 <= other < len(devices):
                devices[other].receive(device.device_id, payload)
print(json.dumps([[device.result for device in devices], max(len(device.run_round({})[0]) for device in devices)]))
"""


def _load_example():
    spec = importlib.util.spec_from_file_location("esp32_example", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


esp32 = _load_example()


def _line(rounds: int) -> list:
    devices = [esp32.Device(device_id) for device_id in (64, 1000, 17)]
    for _ in range(rounds):
        for index, device in enumerate(devices):
            payload, _ = device.run_round({"source": index == 0})
            for other in (index - 1, index + 1):
                if 0 <= other < len(devices):
                    devices[other].receive(device.device_id, payload)
    return devices


def test_esp32_device_computes_a_gradient_over_bytes():
    devices = _line(rounds=6)

    assert [device.result for device in devices] == [0.0, 1.0, 2.0]


def test_esp32_device_lights_the_led_near_the_source():
    devices = _line(rounds=6)

    leds = [device.run_round({"source": index == 0})[1]["led"] for index, device in enumerate(devices)]

    assert leds == [True, True, False]


def test_esp32_device_messages_fit_an_espnow_packet():
    devices = _line(rounds=6)

    assert max(len(device.run_round({})[0]) for device in devices) <= esp32.ESPNOW_MAX_PAYLOAD


def test_esp32_device_forgets_neighbours_that_fell_silent():
    source, device = esp32.Device(1), esp32.Device(2)
    for _ in range(3):
        device.receive(1, source.run_round({"source": True})[0])
        device.run_round({})

    for _ in range(esp32.SILENT_ROUNDS + 1):
        device.run_round({})

    assert device.result == float("inf")


@pytest.mark.skipif(MICROPYTHON is None, reason="micropython is not on the PATH")
def test_esp32_device_runs_on_micropython_with_little_memory(tmp_path):
    build([EXAMPLE], tmp_path)
    (tmp_path / "line.py").write_text(LINE)

    completed = subprocess.run(
        [MICROPYTHON, "-X", f"heapsize={HEAP}", "line.py"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    results, largest_payload = json.loads(completed.stdout)
    assert results == [0.0, 1.0, 2.0]
    assert largest_payload <= esp32.ESPNOW_MAX_PAYLOAD

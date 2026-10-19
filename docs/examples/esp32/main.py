"""
A phyelds device on an ESP32 running MicroPython.

Each board computes its distance, in hops, from the boards whose BOOT button is pressed,
and lights its LED when that distance is below 2. Boards talk over ESP-NOW broadcast: no
Wi-Fi network is needed. Build the program, copy it to each board, and reset them:

    poetry run python -m phyelds.micropython docs/examples/esp32/main.py -o dist
    mpremote cp -r dist/. :
    mpremote reset

A ``Device`` does not touch the hardware, so the same rounds also run on CPython and on
the unix port of MicroPython (see src/tests/examples/test_esp32_example.py).
"""
import time

from phyelds.calculus import aggregate
from phyelds.libraries.device import sense, store
from phyelds.libraries.distances import hops_distance
from phyelds.libraries.spreading import distance_to
from phyelds.vm.device import Device

# Calibration knobs: they depend on the board and on how dense the boards are.
ROUND_MS = 500
SILENT_ROUNDS = 4  # rounds a neighbour is kept after its last message
LED_PIN = 2
BUTTON_PIN = 0  # BOOT, pressed when low
ESPNOW_MAX_PAYLOAD = 250
BROADCAST = b"\xff" * 6


@aggregate
def gradient():
    """Hops to the nearest source; the LED shows the area around it."""
    distance = distance_to(sense("source"), hops_distance())
    store("led", distance < 2)
    return distance


# --8<-- [start:device]
def new_device(device_id):
    """The gradient on a board: messages are bytes, the radio is up to the caller."""
    # Compact paths: integer keys, small enough for an ESP-NOW packet.
    return Device(device_id, gradient, paths="compact", lifetime=SILENT_ROUNDS)


def main():
    """Run the device forever on the board."""
    import espnow  # pylint: disable=import-error,import-outside-toplevel
    import machine  # pylint: disable=import-error,import-outside-toplevel
    import network  # pylint: disable=import-error,import-outside-toplevel

    station = network.WLAN(network.WLAN.IF_STA)
    station.active(True)
    radio = espnow.ESPNow()
    radio.active(True)
    radio.add_peer(BROADCAST)
    led = machine.Pin(LED_PIN, machine.Pin.OUT)
    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    device = new_device(_device_id(station.config("mac")))
    while True:
        deadline = time.ticks_add(time.ticks_ms(), ROUND_MS)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            sender, payload = radio.recv(max(0, time.ticks_diff(deadline, time.ticks_ms())))
            if payload:
                device.receive(_device_id(sender), payload)
        payload = device.run_round({"source": button.value() == 0})
        radio.send(BROADCAST, payload, False)
        led.value(device.outputs["led"])
# --8<-- [end:device]


def _device_id(mac):
    """A device id from the last three bytes of its MAC address."""
    return int.from_bytes(mac[-3:], "big")


if __name__ == "__main__":
    main()

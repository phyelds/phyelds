# MicroPython and the ESP32

phyelds programs run on microcontrollers with [MicroPython](https://micropython.org), such
as the ESP32. The program does not change: the same `@aggregate` functions and the same
libraries run on the board, and boards can talk with devices running CPython.

MicroPython cannot do what `@aggregate` does at run time (rewrite the function to align
its branches), and lacks part of the standard library. So a program is **built** on
CPython before it is copied to the board.

---

## Build and deploy

```bash
poetry run python -m phyelds.micropython main.py -o dist   # main.py: your program
mpremote cp -r dist/. :                                     # copy to the board
mpremote reset                                              # MicroPython runs main.py
```

The build writes into `dist` the given modules and the modules of phyelds they import (the
core only: the simulator is a package of its own), rewritten for MicroPython. The imports are
found by reading the program, so a module imported by a computed name must be named with
`--include phyelds.libraries.gossip` (once per module); with neither modules nor
`--include`, the whole library is written. Each module is rewritten:

- the branches of `@aggregate` functions are aligned ahead of time, exactly as
  `@aggregate` would do at run time, so the alignment paths are the same on every runtime;
- annotations, type expressions and docstrings are removed, and unpacking in tuples and
  lists (`(*hops, last)`) is spelled out;
- the modules MicroPython lacks (`typing`, `dataclasses`, `enum`, `contextvars`, `wrapt`,
  ...) are replaced by small stand-ins in `phyelds._mpy`;
- what MicroPython cannot find out by itself is written down: the fields of dataclasses,
  the members of enums, and the parameters of the functions of the program.

The output is plain Python: you can check it, or run it on CPython.

### Compiled ahead

With `--mpy`, the build compiles the modules of phyelds to `.mpy` files with
[`mpy-cross`](https://docs.micropython.org/en/latest/reference/mpyfiles.html), so that the
board does not compile them when it imports them, which takes more memory than they then
keep. `mpy-cross` must be on the PATH, in the version of MicroPython the board runs:

```bash
pip install "mpy-cross==1.29.*"
poetry run python -m phyelds.micropython main.py -o dist --mpy
```

`--optimize 3` makes the files about 8% smaller, without line numbers in tracebacks. The
modules of the program stay `.py`. MicroPython imports a `.py` before a `.mpy` with the same
name: remove the `.py` files of an older build from the board.

### Pruning

`--prune` leaves out the functions, classes and methods of phyelds that the program never
names: a program that sums a field keeps `sum` and what it calls, not the other methods of
fields. The analysis goes by name and stays on the safe side: a definition stays if its
name appears anywhere else in the build (as a name, an attribute, an import, or a word in a
string), and so do special methods and definitions with decorators that may register them.
So code that is not in the build, such as code typed at the REPL, cannot use what is left
out, and a name the program only computes must appear in it, for instance in a string. The
modules given with `--include` are kept whole.

```bash
poetry run python -m phyelds.micropython main.py -o dist --mpy --prune
```

---

## The device loop

A board is a host like any other (see [the round protocol](index.md#the-round-protocol)):
it runs rounds, and sends its messages to its neighbors. `phyelds.vm.device.Device` runs the
rounds of a device whose messages are bytes: `receive(sender, payload)` keeps the last
message of each neighbor for `lifetime` rounds, and `run_round(sensors)` runs the program
and returns the bytes to send. In this example they travel over ESP-NOW broadcast:

```python
--8<-- "esp32/main.py:device"
```

The complete example, with the radio, the BOOT button as the source and the LED as the
output, is [`docs/examples/esp32/main.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/esp32/main.py).

### Compact paths

State and messages are keyed by the alignment path of each value. By default the key is
the path itself, readable: `"['gradient@0', 'distance_to@1', 'left@1', 'neighbors@1']"`.
`MutableEngine(paths="compact")` keys them by a 30-bit hash of the path instead, which is
lighter on memory and on the radio: in the example a message takes 40 bytes instead of
131, well under the 250 bytes of an ESP-NOW packet. The hash is built as the program enters
each alignment point, from the hash of the point above, so a key costs the same however
deep the path; and it stays a small integer, which a 32-bit board does not allocate.

The hash is the same on every runtime, so a CPython device in compact mode understands a
board. **All the devices that talk to each other must use the same mode**, and the same
version of phyelds from 9.0 on: earlier versions hash paths otherwise.

`paths` also takes an encoding of your own: an object with the two methods of
`DebugPaths` and `CompactPaths` (in `phyelds.vm.internal`). `segment(parent, name,
counter)` encodes an alignment point as the program enters it: its name (the function, the
branch, or the key given to `align`), how many points its parent entered before it, and
the segment of its parent. `key(path)` turns the segments of a path into a key that the
[wire format](#the-wire-format) can send. Numbers from a table of names, for instance, keep
keys short and still readable: in the example a message takes 53 bytes.

```python
CODES = {
    "gradient": 1, "distance_to": 2, "hops_distance": 3,  # the functions of the example
    "remember": 4, "neighbors": 5, "left": 6, "right": 7,  # the calculus and its branches
}


class Numbered:
    """gradient@0, then neighbors@1, as "1.0/5.1"."""

    def segment(self, parent, name, counter):
        return f"{CODES[name]}.{counter}"

    def key(self, path):
        return "/".join(path)


device = Device(device_id, gradient, paths=Numbered())
```

The table must name every alignment point the program enters, those of the libraries and
of branches (`left`, `right`) included, and all the devices must share it. Keys can be
tuples too, but the wire format tags them, so they take more room than strings.

### The wire format

`phyelds.data.codec` turns the messages of a device into bytes and back:

```python
from phyelds.data.codec import decode, encode

payload = encode(engine.get().cooldown())   # bytes to send
messages = {sender: decode(payload)}        # inbox for the next round
```

The bytes are JSON, with a tag for what JSON cannot say: tuples, sets, non-string keys,
infinities, fields, and the dataclasses and sentinels of the libraries. To send a type of
your own, register it on every device with `register(MyDataclass)`.

### Messages for each neighbor

A program that exchanges a field, a different value for each neighbor, sends the whole
field to all of them: the message grows with the neighbors, and with a field of floats it
no longer fits an ESP-NOW packet beyond about ten. `Device(..., per_neighbor=True)` sends
each neighbor only its own value instead. `run_round` then returns the message for every
neighbor, with each field at its default, and `device.addressed` maps each neighbor the
device heard from to the message addressed to it, with each field reduced to its value for
that neighbor. A neighbor builds its field from the values addressed to it, as it would
from the whole fields, so the program computes the same:

```python
payload = device.run_round(sensors)
for neighbor, addressed in device.addressed.items():  # first: see below
    espnow.send(BROADCAST, addressed)                   # or to the MAC of the neighbor
espnow.send(BROADCAST, payload)
```

A device leaves out the messages addressed to other devices, so all of them can go out on
broadcast, without registering the neighbors as peers. It also leaves out a message for
every neighbor while it keeps one addressed to it since its last round: send the addressed
messages first. `addressed` is empty when the program sends no field, and the message for
every neighbor then serves them all. The devices that receive these messages need a
version of phyelds with `per_neighbor`: an older one would take a message addressed to
another device for its own.

Each message stays the same size whatever the neighbors, but there is one more for each of
them. With a field of floats, compact paths and device ids of 3 bytes (with 43 bytes of
ESP-NOW frame around each message):

| Neighbors | Whole field | Per neighbor: largest message | Messages | Bytes on air, whole / per neighbor |
|---|---|---|---|---|
| 2 | 103 B | 44 B | 3 | 146 / 242 |
| 10 | 245 B | 45 B | 11 | 288 / 939 |
| 20 | 416 B | 45 B | 21 | 459 / 1814 |

So send the whole field while it fits a packet, and messages for each neighbor when it does
not: they take more time on air.

---

## What works

Every building block of the calculus and every library runs on MicroPython, and its tests
check that each one gives the same results and messages as on CPython (see
`src/tests/micropython`). A few differences remain:

| On MicroPython | Instead |
|---|---|
| An accumulation given as a lambda is called with the data only: `cast_from(source, 0, lambda edge, data: ...)` fails. | Define a function at the top of the program; the build records its parameters. |
| A value on the left of a comparison with a state fails: `2 < count`. | Put the state on the left: `count > 2`. |
| A state is not an instance of the type of its value: `isinstance(count, int)` is false. | Use `count.value`. |
| `field.data` is an `OrderedDict`, never equal to a `dict`. | Compare `dict(field.data)`. |
| Floats are 32-bit on most ports, the ESP32 included. | Expect small differences in distances. |

---

## Memory

The heap a board needs depends on how the program is built. For the minimal program of the
tests (`src/tests/micropython/minimal.py`: a counter and the ids of the neighbors, on three
devices exchanging bytes), on the 64-bit unix port of MicroPython 1.29:

| Build | phyelds on the board | Heap to start | Heap kept after the rounds |
|---|---|---|---|
| `.py` | 29 KB of files | ~82 KB | 43 KB |
| [`--mpy`](#compiled-ahead) | 15 KB of files | ~56 KB | 43 KB |
| `--mpy` [`--prune`](#pruning) | 12 KB of files | ~52 KB | 37 KB |
| [frozen](#frozen-into-the-firmware) | 24 KB of firmware | ~30 KB | 21 KB |
| frozen, `--prune` | 17 KB of firmware | ~28 KB | 19 KB |

A `.py` module is compiled when it is imported, which briefly needs more memory than it then
keeps: hence the larger heap to start. Objects are about half as large on the 32-bit ESP32,
which without PSRAM has roughly 100 KB free. Libraries add to it: the calculus with
`spreading` and the codec keep about 50 KB of heap once imported as `.mpy`, and all the
libraries about 90 KB, so import only those the program uses. The ESP32 example runs, three
devices in one process, in a 128 KB heap on the unix port. The tests keep the heap the
minimal program needs under a budget, so that regressions show up.

### Frozen into the firmware

The leanest option is a MicroPython firmware of your own, with phyelds frozen into it: its
bytecode then stays in flash, and the heap only holds the objects the program makes. Build
without `--mpy` (freezing compiles the modules itself), and write a
[manifest](https://docs.micropython.org/en/latest/reference/manifest.html) next to `dist`:

```python
include("$(PORT_DIR)/boards/manifest.py")  # what the board freezes by default
package("phyelds", base_path="dist")
```

Then build MicroPython for the board with it, e.g. for an ESP32:

```bash
make -C ports/esp32 BOARD=ESP32_GENERIC FROZEN_MANIFEST=/absolute/path/to/manifest.py
```

Copy only the modules of the program to the board: a `phyelds` folder on the board would be
imported instead of the frozen one.

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
131, well under the 250 bytes of an ESP-NOW packet.

The hash is the same on every runtime, so a CPython device in compact mode understands a
board. **All the devices that talk to each other must use the same mode.**

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

On the 64-bit unix port of MicroPython, the calculus with `spreading` and the codec keep
about 64 KB of heap once imported, and all the libraries about 118 KB. Objects are about
half as large on the 32-bit ESP32, which without PSRAM has roughly 100 KB free: import
only the libraries the program uses. Modules are compiled when they are imported, which
briefly needs more memory than they then keep, unless they are [compiled ahead](#compiled-ahead):
the minimal program of the tests (`src/tests/micropython/minimal.py`, a counter and the ids
of the neighbors on three devices) starts in about 82 KB of heap as `.py`, in 56 KB as
`.mpy`, and in 52 KB [pruned](#pruning). The ESP32 example runs, three devices in one process, in a 128 KB heap on the unix
port.

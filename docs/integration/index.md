# Running phyelds anywhere

The bundled simulator is just one host. Any system that can, for each device,
run Python code periodically and deliver messages to its neighbors can run phyelds
programs: a robotics simulator, real robots, a game engine, a network simulator.

## The round protocol

A phyelds program does not know where it runs. For each device and each round, the
host:

1. builds a **`NodeContext`** with the device id and a dictionary of **sensors**
   (by convention `position` and `time`, plus anything the program `sense`s);
2. collects the **inbox**: the last *outbox* of each current neighbor, as
   `{neighbor_id: outbox}`;
3. loads the **state** the device kept from its previous round (`{}` the first time);
4. sets up a fresh engine and runs the `@aggregate` program;
5. saves the new **outbox** (`cooldown()`), the new **state** (`state_trace()`) and
   the **outputs** the program `store`d, and sends the outbox to the neighbors.

```python
--8<-- "custom_runtime.py:run_round"
```

The complete, runnable example, which drives a line of devices with plain Python
objects, is
[`docs/examples/custom_runtime.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/custom_runtime.py).

## Rules for a host

- **Call `cooldown()` before `state_trace()`.** `cooldown` also drops the state the
  program did not use in this round; reading the trace first would keep stale state.
- **Use one engine per round.** `phyelds.engine` is a `ContextVar`: set a fresh
  `MutableEngine` before each round. Being a `ContextVar`, each thread or asyncio
  task sees its own engine.
- **Deliver copies.** Outboxes and states are plain dictionaries of your values. A
  real network serialises them; an in-process host should copy them, or devices
  will be able to mutate each other's state.
- **Keep the state per device.** The state is opaque: store it as it is and give it
  back in the next round. It must survive between rounds, but it need not survive a
  restart (the program re-converges).
- **Send to the current neighbors only.** Neighbors that disappear simply stop
  appearing in the inbox; the program adapts.
- **Read actuations from the outputs.** Programs act on the world through
  `store(name, value)`; the host applies them (moving a robot, switching a LED).
- **Unwrap the result.** A program may return a `State` proxy: use `.value` to get
  the plain value.

## Two ways to integrate

- **Reuse the bundled simulator** with a custom `Environment`, when the host can be
  stepped from Python: the simulator's runner already implements the protocol
  (`phyelds.simulator.runner.aggregate_program_runner`), and you only map the host's
  state to nodes. This is how [VMAS](vmas.md) is integrated.
- **Drive rounds yourself**, as in the example above, when the host owns the loop
  (a real device, an external simulator calling back into Python).

# Running phyelds anywhere

The phyelds simulator is just one host. Any system that can, for each device, run Python code periodically and deliver messages to its neighbors can run **phyelds** programs: a robotics simulator, real robots, a game engine, or a network simulator.

---

## The round protocol

A phyelds program does not know where it runs. For each device and each round, the host goes through the three phases of the [execution model](../concepts/aggregate-programs.md#the-execution-model-sense-compute-act):

<div class="ph-steps">
  <div class="ph-step ph-step--orange">
    <div class="ph-step-title">1. Sense</div>
    <p>Build <code>NodeContext(id, sensors)</code>, gather the <code>inbox</code> from the current neighbors, and load the <code>state</code> of the device.</p>
  </div>
  <div class="ph-step">
    <div class="ph-step-title">2. Compute</div>
    <p>Call <code>setup(context, inbox, state)</code> on a fresh engine, run the <code>@aggregate</code> function, and unwrap <code>result.value</code> if it returns a <code>State</code> proxy.</p>
  </div>
  <div class="ph-step ph-step--purple">
    <div class="ph-step-title">3. Act</div>
    <p>Call <code>cooldown()</code> (which returns the <code>outbox</code> and prunes unused state), then save <code>state_trace()</code> and apply <code>outputs</code>.</p>
  </div>
</div>

In detail, the host:

1. Builds a **`NodeContext`** with the device ID and a dictionary of **sensors** (by convention `position` and `time`, plus anything the program `sense`s);
2. Collects the **inbox**: the last *outbox* of each current neighbor, as `{neighbor_id: outbox}`;
3. Loads the **state** the device kept from its previous round (`{}` the first time);
4. Sets a fresh `MutableEngine` in `engine` (a `ContextVar`), calls `engine.get().setup(context, inbox, state)`, and runs the `@aggregate` program;
5. Saves the new **outbox** (`cooldown()`), the new **state** (`state_trace()`), and the **outputs** the program `store`d, and sends the outbox to the neighbors.

```python
--8<-- "custom_runtime.py:run_round"
```

The complete, runnable example, which drives a line of devices with plain Python objects, is [`docs/examples/custom_runtime.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/custom_runtime.py).

---

## Rules for a host

- **Call `cooldown()` before `state_trace()`.** `cooldown` also drops the state the program did not use in this round; reading the trace first would keep stale state.
- **Use one engine per round.** `phyelds.vm.engine` is a `ContextVar`: set a fresh `MutableEngine` before each round. Being a `ContextVar`, each thread or `asyncio` task sees its own engine.
- **Deliver copies.** Outboxes and states are plain dictionaries of your values. A real network serializes them; an in-process host should copy them, or devices will be able to mutate each other's state.
- **Keep the state per device.** The state is opaque: store it as it is and give it back in the next round. It must survive between rounds, but it need not survive a restart (the program re-converges).
- **Send to the current neighbors only.** Neighbors that disappear simply stop appearing in the inbox; the program adapts.
- **Read actuations from the outputs.** Programs act on the world through `store(name, value)`; the host applies them (moving a robot, switching a LED).
- **Unwrap the result.** A program may return a `State` proxy: use `.value` to get the plain value.

---

## Ways to integrate

- **Reuse the phyelds simulator** with a custom `Environment`, when the host can be stepped from Python: the simulator's runner already implements the protocol (`phyelds.simulator.runner.aggregate_program_runner`), and you only map the host's state to nodes. This is how [VMAS](vmas.md) is integrated.
- **Run rounds from another simulator**, when it owns the agents and the time: [Mesa](mesa.md) models do it with `phyelds-mesa`, which runs a round on every agent at each step of the model.
- **Drive rounds yourself**, as in the example above, when the host owns the loop (a real device, ROS node, or an external simulator calling back into Python). Microcontrollers are hosts of this kind: see [MicroPython and the ESP32](micropython.md).

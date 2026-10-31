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
- **Drive rounds yourself**, as in the example above, when the host owns the loop (a real device, ROS node, or an external simulator calling back into Python).
- **Run each device on its own**, when every device has its own process and sends its messages as bytes over a radio: `phyelds.vm.device.Device` runs its rounds, and the host only moves the bytes. This is how [MicroPython and the ESP32](micropython.md) and [Webots](webots.md) robots run phyelds.

- **Embed Python in a native simulator**, when it calls C++ controllers in one process: [ARGoS](argos.md) runs a `Device` per robot and transports its messages over the simulated radio.

---

## Ideal and delivered neighborhoods

A host builds the inbox of a device in one of two ways:

- **Ideal**: the host computes the neighbors, from positions or a graph, and hands the device the last outbox of each one. No message is ever lost or late. The simulator, VMAS and Mesa work this way.
- **Delivered**: the inbox is what the transport actually delivered. The neighbors are the devices heard from, and a lost message is simply missing. Webots, ARGoS and the ESP32 work this way, through a `Device`.

A host that simulates a network, such as a network simulator or a V2X model, must use the delivered model. An inbox built from positions around the network would hide the losses and delays the network is there to show.

---

## Rounds of each host

Each host makes its own choices about time, scheduling and membership. A new host can pick the row closest to it as the reference to match.

| Host | Clock | Rounds | Neighborhood | Message lifetime | Join and leave |
|---|---|---|---|---|---|
| Simulator | The time of its events | One event per node per period. Nodes due at the same time run one after the other, in no set order, and read what their neighbors already sent in this round | Ideal: the neighborhood function | The last outbox of a neighbor, while it is a neighbor | Add a node and schedule its rounds; a removed node stops running |
| [VMAS](vmas.md) | The simulator's | As the simulator; VMAS steps in an event of its own | Ideal, on the positions of the VMAS agents | As the simulator | The agents of the scenario, fixed |
| [Mesa](mesa.md) | `model.time` | Synchronous: each `run_round` runs every agent once, and each agent reads what its neighbors sent in the previous round | Ideal: `within`, `cell_neighbors` or any function | One round | An agent joins when it is among the agents of a round; one missing from a round is forgotten, with its state and messages |
| [Webots](webots.md) | The simulation time | One per robot every `--steps-per-round` steps, each robot in its own process. Synchronous, as Webots delivers a message in the next step | Delivered: the robots its `Emitter` reaches | One round | The robots of the world; one that stops sending is forgotten at the next round |
| [ARGoS](argos.md) | The simulation clock | One per robot per tick, one robot at a time. Synchronous, as the radio delivers on the next tick | Delivered: the range-and-bearing or simple radios | One round | The robots of the experiment; a reset clears the state and the messages |
| [MicroPython](micropython.md) | The clock of each device | Each device on its own, with a round every `ROUND_MS`. Asynchronous: the rounds of neighbors are not aligned | Delivered: the ESP-NOW broadcasts received | `lifetime` rounds (4 in the example) | A device joins with its first message, and is forgotten after `lifetime` silent rounds |

Two schedules cover these hosts, and `Device` reproduces both round by round, on the same topology:

- **Synchronous** (Mesa, Webots, ARGoS): every device runs its round, and then every device sends. `packages/phyelds-mesa/tests/test_runtime_matches_devices.py` checks Mesa against such a loop.
- **Sequential** (the simulator and VMAS): each device sends right after its own round, so a device reads what its neighbors already sent in the current round. `src/tests/vm/test_device_matches_simulator.py` checks the simulator against such a loop.

When the rounds of neighbors are not aligned, a device can run two rounds between two messages of the same neighbor. This happens with asynchronous devices, or over a simulated network. With `lifetime=1`, such neighbors drop in and out from one round to the next. Keep their messages for two rounds or more.

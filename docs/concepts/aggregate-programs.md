# Thinking in fields: aggregate programs

Aggregate computing programs a **collective** instead of a single device. Rather than writing message handlers, socket loops, or state machines for individual nodes, you write **one function** that describes how a global distributed data structure—a **computational field**—evolves over space and time.

For the theoretical foundations, see the [main paper on aggregate computing](https://www.sciencedirect.com/science/article/pii/S235222081930032X).

---

## Local execution, global meaning

A **computational field** assigns a value to every device at every moment in time (for example: a field of temperatures, a field of distances from an exit, or a field of cluster IDs). No single coordinator holds the whole field; instead, it emerges from every device repeatedly running the same program and exchanging values only with its immediate neighbors.

<div class="ph-figure">
<svg viewBox="0 0 820 265" role="img" aria-label="Local view of one device versus the global computational field across the network">
  <defs>
    <marker id="ph-arr-m" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-magenta)" />
    </marker>
    <marker id="ph-arr-o" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-orange)" />
    </marker>
    <linearGradient id="ph-grad-bridge" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#c55308" />
      <stop offset="100%" stop-color="#b4136f" />
    </linearGradient>
  </defs>

  <!-- Left Card: Local View -->
  <rect x="10" y="12" width="335" height="240" rx="10" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="177" y="36" text-anchor="middle" font-size="13" font-weight="700" fill="var(--ph-diag-orange)">1. LOCAL VIEW (one device, one round)</text>

  <!-- Communication radius -->
  <circle cx="177" cy="142" r="84" fill="var(--ph-diag-soft-orange)" stroke="var(--ph-diag-orange)" stroke-width="1.2" stroke-dasharray="5,4" />

  <!-- Bidirectional arrows between Device i and neighbors -->
  <line x1="112" y1="98" x2="148" y2="122" stroke="var(--ph-diag-orange)" stroke-width="1.8" marker-end="url(#ph-arr-o)" />
  <line x1="154" y1="116" x2="118" y2="92" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-arr-m)" />

  <line x1="242" y1="98" x2="206" y2="122" stroke="var(--ph-diag-orange)" stroke-width="1.8" marker-end="url(#ph-arr-o)" />
  <line x1="200" y1="116" x2="236" y2="92" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-arr-m)" />

  <line x1="177" y1="200" x2="177" y2="172" stroke="var(--ph-diag-orange)" stroke-width="1.8" marker-end="url(#ph-arr-o)" />
  <line x1="185" y1="172" x2="185" y2="200" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-arr-m)" />

  <!-- Neighbor nodes -->
  <circle cx="98" cy="84" r="18" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-orange)" stroke-width="2" />
  <text x="98" y="88" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ph-diag-text)">Nbr A</text>

  <circle cx="256" cy="84" r="18" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-orange)" stroke-width="2" />
  <text x="256" y="88" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ph-diag-text)">Nbr B</text>

  <circle cx="177" cy="218" r="18" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-orange)" stroke-width="2" />
  <text x="177" y="222" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ph-diag-text)">Nbr C</text>

  <!-- Central Device i -->
  <circle cx="177" cy="142" r="26" fill="#b4136f" />
  <text x="177" y="139" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Device i</text>
  <text x="177" y="152" text-anchor="middle" font-size="9.5" class="ph-code" fill="#fde047">@aggregate</text>

  <!-- Legend pills inside local view -->
  <text x="52" y="242" font-size="10.5" fill="var(--ph-diag-orange)" font-weight="600">→ inbox (from neighbors)</text>
  <text x="200" y="242" font-size="10.5" fill="var(--ph-diag-magenta)" font-weight="600">→ outbox (to neighbors)</text>

  <!-- Center Bridge: Emerges across space & time -->
  <line x1="352" y1="132" x2="462" y2="132" stroke="url(#ph-grad-bridge)" stroke-width="3" marker-end="url(#ph-arr-m)" />
  <rect x="355" y="96" width="104" height="28" rx="14" fill="var(--ph-diag-Soft-magenta)" stroke="var(--ph-diag-magenta)" stroke-width="1.2" />
  <text x="407" y="108" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-magenta)">Emerges across</text>
  <text x="407" y="119" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-magenta)">space &amp; time</text>

  <!-- Right Card: Global View -->
  <rect x="472" y="12" width="338" height="240" rx="10" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="641" y="36" text-anchor="middle" font-size="13" font-weight="700" fill="var(--ph-diag-magenta)">2. GLOBAL VIEW (the computational field)</text>

  <!-- Mesh edges -->
  <g stroke="var(--ph-diag-muted)" stroke-width="1.4" opacity="0.45">
    <line x1="525" y1="190" x2="585" y2="145" />
    <line x1="525" y1="190" x2="595" y2="205" />
    <line x1="525" y1="190" x2="530" y2="110" />
    <line x1="530" y1="110" x2="585" y2="145" />
    <line x1="530" y1="110" x2="605" y2="80" />
    <line x1="585" y1="145" x2="595" y2="205" />
    <line x1="585" y1="145" x2="605" y2="80" />
    <line x1="585" y1="145" x2="665" y2="135" />
    <line x1="595" y1="205" x2="675" y2="198" />
    <line x1="595" y1="205" x2="665" y2="135" />
    <line x1="605" y1="80" x2="665" y2="135" />
    <line x1="605" y1="80" x2="690" y2="75" />
    <line x1="665" y1="135" x2="690" y2="75" />
    <line x1="665" y1="135" x2="675" y2="198" />
    <line x1="665" y1="135" x2="755" y2="140" />
    <line x1="690" y1="75" x2="755" y2="82" />
    <line x1="690" y1="75" x2="755" y2="140" />
    <line x1="675" y1="198" x2="755" y2="140" />
    <line x1="675" y1="198" x2="755" y2="202" />
    <line x1="755" y1="82" x2="755" y2="140" />
    <line x1="755" y1="140" x2="755" y2="202" />
  </g>

  <!-- Mesh nodes colored by field value (plasma-like scale from 0.0 source to 3.2) -->
  <circle cx="525" cy="190" r="17" fill="#f59e0b" stroke="#ffffff" stroke-width="2" />
  <text x="525" y="194" text-anchor="middle" font-size="10.5" font-weight="700" fill="#1f1a24">0.0</text>

  <circle cx="530" cy="110" r="15" fill="#ea580c" />
  <text x="530" y="114" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">1.0</text>

  <circle cx="585" cy="145" r="15" fill="#ea580c" />
  <text x="585" y="149" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">1.1</text>

  <circle cx="595" cy="205" r="15" fill="#e11d48" />
  <text x="595" y="209" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">1.2</text>

  <circle cx="605" cy="80" r="15" fill="#db2777" />
  <text x="605" y="84" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">1.9</text>

  <circle cx="665" cy="135" r="15" fill="#b4136f" />
  <text x="665" y="139" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">2.1</text>

  <circle cx="675" cy="198" r="15" fill="#9d174d" />
  <text x="675" y="202" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">2.2</text>

  <circle cx="690" cy="75" r="15" fill="#7e22ce" />
  <text x="690" y="79" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">2.7</text>

  <circle cx="755" cy="140" r="15" fill="#6b21a8" />
  <text x="755" y="144" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">3.0</text>

  <circle cx="755" cy="202" r="15" fill="#581c87" />
  <text x="755" y="206" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">3.1</text>

  <circle cx="755" cy="82" r="15" fill="#4c1d95" />
  <text x="755" y="86" text-anchor="middle" font-size="10" font-weight="700" fill="#ffffff">3.4</text>

  <text x="641" y="242" text-anchor="middle" font-size="10.5" fill="var(--ph-diag-muted)">Each node holds one value; together they form a space-time field</text>
</svg>
</div>

Every aggregate function therefore has **two readings**:

- **Local reading**: what one device computes in a single step (for instance, *"take the minimum of my neighbors' numbers and add 1"*).
- **Global reading**: what field the entire network converges to over time (for instance, *"the shortest-path distance of every device from the nearest source"*).

You design by composing **global** fields, while Python executes the **local** steps on each device.

---

## The execution model: Sense → Compute → Act

Every device executes the aggregate program in periodic, asynchronous **rounds**. In each round, a device goes through three phases:

<div class="ph-figure">
<svg viewBox="0 0 820 220" role="img" aria-label="The three phases of an aggregate round: Sense, Compute, and Act">
  <defs>
    <marker id="ph-round-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-magenta)" />
    </marker>
  </defs>

  <!-- Column 1: SENSE -->
  <rect x="12" y="10" width="235" height="200" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="130" y="32" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--ph-diag-orange)">1. SENSE (INPUTS)</text>

  <rect x="26" y="46" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="130" y="64" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Device Sensors</text>
  <text x="130" y="80" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">sense("temp"), local_position()</text>

  <rect x="26" y="98" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="130" y="116" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Previous Local State</text>
  <text x="130" y="132" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">from remember / exchange</text>

  <rect x="26" y="150" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="130" y="168" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Neighbor Inbox</text>
  <text x="130" y="184" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">aligned neighbors' last outboxes</text>

  <!-- Arrows from SENSE to COMPUTE -->
  <path d="M 233 67 C 265 67, 265 102, 294 108" fill="none" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />
  <line x1="233" y1="119" x2="294" y2="119" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />
  <path d="M 233 171 C 265 171, 265 136, 294 130" fill="none" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />

  <!-- Column 2: COMPUTE -->
  <rect x="300" y="54" width="220" height="122" rx="10" fill="#b4136f" />
  <text x="410" y="84" text-anchor="middle" font-size="12.5" font-weight="700" fill="#fde047">2. COMPUTE</text>
  <text x="410" y="110" text-anchor="middle" font-size="12" font-weight="700" class="ph-code" fill="#ffffff">@aggregate program()</text>
  <text x="410" y="132" text-anchor="middle" font-size="10.5" fill="#fce7f3">Runs top-to-bottom on the device,</text>
  <text x="410" y="148" text-anchor="middle" font-size="10.5" fill="#fce7f3">aligning every call along its path</text>

  <!-- Arrows from COMPUTE to ACT -->
  <path d="M 520 108 C 550 102, 550 67, 581 67" fill="none" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />
  <line x1="520" y1="119" x2="581" y2="119" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />
  <path d="M 520 130 C 550 136, 550 171, 581 171" fill="none" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-round-arr)" />

  <!-- Column 3: ACT -->
  <rect x="573" y="10" width="235" height="200" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="690" y="32" text-anchor="middle" font-size="12.5" font-weight="700" fill="var(--ph-diag-magenta)">3. ACT (OUTPUTS)</text>

  <rect x="587" y="46" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="690" y="64" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Actuations &amp; Metrics</text>
  <text x="690" y="80" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">store("motor", v), return value</text>

  <rect x="587" y="98" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="690" y="116" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Updated Local State</text>
  <text x="690" y="132" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">kept for this device's next round</text>

  <rect x="587" y="150" width="207" height="42" rx="6" fill="var(--ph-diag-bg)" stroke="var(--ph-diag-border)" />
  <text x="690" y="168" text-anchor="middle" font-size="11.5" font-weight="700" fill="var(--ph-diag-text)">Outbox Packet</text>
  <text x="690" y="184" text-anchor="middle" font-size="10" class="ph-code" fill="var(--ph-diag-muted)">sent to current neighbors</text>
</svg>
</div>

1. **Sense**: the runtime gathers the device's current sensor readings, the state saved at the end of its own previous round, and the most recent messages received from its current neighbors.
2. **Compute**: the device runs the `@aggregate` function from top to bottom. Whenever the code calls `remember(...)`, it reads from the previous state; whenever it calls `neighbors(...)`, it reads the neighbors' values for that exact call site and records its own value for the outbox.
3. **Act**: the runtime stores the new local state for the next round, exposes any outputs written with `store(...)` to the platform (actuators, logs, metrics), and broadcasts the single outbox packet to neighboring devices.

Rounds across different devices do **not** need to be synchronized, and devices can move, join, or leave at any time. Because every round recomputes the field from fresh inputs, aggregate programs naturally **self-heal** when the network topology changes.

---

## How space and time combine

All collective behaviors in **phyelds** come from combining just four mechanisms:

| Mechanism | Primitive | What it gives you |
| --- | --- | --- |
| **Space only** | [`neighbors(x)`](neighborhood-field.md) | 1-hop perception: compare or aggregate values across immediate neighbors |
| **Time only** | [`remember(init)`](state.md) | Local memory: counters, filters, timers, and state machines on a single node |
| **Space + Time** | `remember` + `neighbors`, or [`exchange(init)`](neighborhood-field.md#exchange) | Global propagation: information travels hop-by-hop across the whole network (gradients, broadcasts, collections, gossip) |
| **Domain splitting** | [`if` / `align`](alignment.md), [`@process`](../libraries/self-organisation.md#aggregate-processes-phyeldslibrariesprocesses) | Network partitioning: split devices into independent sub-networks that do not mix messages |

---

## The building blocks at a glance

| Construct | Field calculus | What it does |
| --- | --- | --- |
| [`@aggregate`](alignment.md) | function call ($f$) | Marks a function as part of the aggregate computation and aligns its branches |
| [`remember`](state.md) | `rep` | Keeps local state that survives from one round to the next |
| [`neighbors`](neighborhood-field.md) | `nbr` | Shares a value with neighbors and returns their values as a `NeighborhoodField` |
| [`exchange`](neighborhood-field.md#exchange) | `exchange` | Evolves state and sends (possibly distinct, per-neighbor) values in one step |
| [`if` / `align`](alignment.md) | branching | Isolates branches into separate, non-interfering communication domains |
| `sense`, `store`, `local_id` | sensors / actuators | Reads device sensors and writes actuation/metric outputs (`phyelds.libraries.device`) |

---

## Pragmatic and Pythonic

Most aggregate computing frameworks (such as ScaFi, Protelis, or FCPP) enforce a strictly functional style. **phyelds** is intentionally pragmatic: aggregate programs are ordinary Python functions where you can use standard loops, dictionaries, classes, and controlled mutability.

!!! tip "Three golden rules to keep in mind"
    Because Python does not enforce purity at compile time, keep these three rules in mind (see [Common pitfalls](../pitfalls.md) for concrete examples):

    1. **Decorate every aggregate helper with `@aggregate`** so its calls and `if`/`else` branches are properly aligned across devices.
    2. **Never call `neighbors` a data-dependent number of times** (e.g., inside a `for` loop whose length varies from device to device).
    3. **Keep device state in `remember`, not in Python globals or mutated neighbor objects**, because all simulated nodes share the same Python process.

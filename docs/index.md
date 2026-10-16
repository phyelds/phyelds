# phyelds

**phyelds** is a lightweight, Pythonic toolkit for *aggregate computing*: you write **one program** that describes the behavior of a whole collective (a swarm of robots, a sensor network, a fleet of devices), and every device runs it asynchronously, exchanging values only with its immediate neighbors.

```bash
pip install phyelds             # core library and discrete-event simulator
pip install "phyelds[jupyter]"  # optional: live rendering inside Jupyter notebooks
pip install phyelds-vmas        # optional: VMAS multi-robot simulator integration
```

**phyelds** requires Python 3.12 or later.

---

## Follow the learning path

The documentation is organized as a linear journey from zero to advanced collective systems:

<div class="grid cards" markdown>

- **1. [Thinking in fields](concepts/aggregate-programs.md)** — Understand computational fields, the *Sense → Compute → Act* round lifecycle, and the local vs. global reading of a program.
- **2. [Interactive 3D walkthrough](walkthrough/index.md)** — From a field of sensor readings to a channel split into separate networks, step by step: watch asynchronous rounds in 3D, next to the same fields at infinite density.
- **3. [Step-by-step tutorial](tutorial.md)** — Build the gradient from scratch, watch it self-heal when the network changes, and compose spreading + collection into a communication channel.
- **4. [Browser playground](playground/index.md)** — Edit and run aggregate programs directly in your browser (via Pyodide) with nothing to install.
- **5. [Core concepts](concepts/state.md) & [Common pitfalls](pitfalls.md)** — Master [`remember`](concepts/state.md), [`NeighborhoodField` & `exchange`](concepts/neighborhood-field.md), [`@aggregate` alignment](concepts/alignment.md), and the mistakes to avoid.
- **6. [Standard libraries](concepts/libraries.md)** — Ready-to-use blocks for [spreading, collection & gossip](libraries/spreading-and-collect.md), [leader election & `@process` bubbles](libraries/self-organisation.md), and [time & spatial/temporal logic](libraries/time-and-logic.md).
- **7. [Simulator](simulator.md) & [Integration](integration/index.md)** — Run experiments with animations and CSV export, or embed phyelds into [VMAS](integration/vmas.md) and custom robot runtimes.

</div>

---

## A taste of phyelds

```python
from phyelds.calculus import aggregate, neighbors, remember

@aggregate
def hop_gradient(source: bool) -> float:
    set_distance, distance = remember(float("inf"))
    through_neighbors = neighbors(distance) + 1
    nearest = min(through_neighbors.exclude_self().values(), default=float("inf"))
    set_distance(0 if source else nearest)
    return distance
```

Every device runs these five lines; together, they compute the shortest-path distance of every device from the nearest source, and automatically repair the field when sources move or links change:

![A distance gradient on an irregular network](assets/gradient-self-healing.gif){ width="480" }

[Explore the 3D Walkthrough](walkthrough/index.md){ .md-button .md-button--primary }
[Try it in the playground](playground/index.md#example=self_healing){ .md-button }
[Start with Thinking in Fields](concepts/aggregate-programs.md){ .md-button }

---

## Heritage & acknowledgments

**phyelds** builds upon over a decade of research and open-source tools in spatial and aggregate computing—bringing ideas from **[Proto](https://proto.bbn.com/)**, **[Protelis](https://protelis.github.io/)**, **[ScaFi](https://scafi.github.io/)**, **[FCPP](https://fcpp.github.io/)**, and **[Collektive](https://github.com/Collektive/collektive)** into a pragmatic, Python-native library.

- **Main contributors**: [Gianluca Aguzzi](https://github.com/cric96) and [Davide Domini](https://github.com/davidedomini).
- **Acknowledgments**: special thanks to **Mirko Viroli**, **Danilo Pianini**, **Roberto Casadei**, and **Giorgio Audrito** for the insightful discussions and foundational work that made this project possible.

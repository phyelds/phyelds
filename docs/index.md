---
hide:
  - navigation
  - toc
---

<div class="ph-hero" markdown>
<div markdown>

<span class="ph-eyebrow">Aggregate computing for Python</span>

# Program the <span class="ph-gradient-text">collective</span>, not the device

<p class="ph-lead">
<strong>phyelds</strong> is a lightweight, Pythonic toolkit for aggregate computing. You write
<strong>one function</strong> for a whole collective (a swarm of robots, a sensor network,
a fleet of devices) and every device runs it in asynchronous rounds, exchanging values
only with its immediate neighbors.
</p>

<div class="ph-actions" markdown>
[Get started](concepts/aggregate-programs.md){ .md-button .md-button--primary }
[3D walkthrough](walkthrough/index.md){ .md-button }
[Playground](playground/index.md#example=self_healing){ .md-button }
</div>

```bash
pip install phyelds-simulator
```

<p class="ph-note">
Python 3.12 or later. This installs phyelds and its simulator; <code>pip install phyelds</code>
alone is the core, to run programs on a runtime of your own. Optional:
<code>pip install "phyelds-simulator[jupyter]"</code> for live rendering in Jupyter notebooks,
<code>pip install phyelds-vmas</code> for the VMAS multi-robot simulator,
<code>pip install phyelds-mesa</code> for Mesa agent-based models,
<code>pip install phyelds-webots</code> for the Webots robot simulator.
</p>

</div>
<figure markdown>
![A distance gradient, in 3D, repairing itself as its source is dragged across the network](assets/hero.gif#only-light)
![A distance gradient, in 3D, repairing itself as its source is dragged across the network](assets/hero-dark.gif#only-dark)
<figcaption markdown>In the [playground](playground/index.md#example=self_healing), a distance gradient repairs itself as its source is dragged across the network.</figcaption>
</figure>
</div>

## Why phyelds

<div class="grid cards" markdown>

-   :material-vector-polyline:{ .lg .middle } __One program, a whole collective__

    ---

    Describe the global behavior once, as a Python function: every device runs the same
    code on its own sensors and its neighbors' messages.

-   :material-autorenew:{ .lg .middle } __Self-healing by construction__

    ---

    Every round recomputes the field from fresh inputs, so it repairs itself when devices
    move, fail or join.

-   :material-language-python:{ .lg .middle } __Just Python__

    ---

    Ordinary functions, loops, dictionaries and dataclasses: `@aggregate` keeps the
    messages of the devices aligned.

-   :material-toolbox-outline:{ .lg .middle } __Batteries included__

    ---

    Gradients, collection, gossip, leader election, processes, time and logic, and a
    simulator that renders animations.

</div>

## A taste of phyelds

<div class="ph-split" markdown>

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

<div markdown>

![The hop-count gradient spreading along a line of ten devices](assets/gradient-hops.gif#only-light)
![The hop-count gradient spreading along a line of ten devices](assets/gradient-hops-dark.gif#only-dark)

Every device runs these five lines: it remembers its estimate, shares it with its
neighbors, and keeps the smallest one plus one hop. Together, the devices compute how many
hops separate each of them from the nearest source (above, on a line of ten devices), and
they recompute it when sources move or links change.

The [tutorial](tutorial.md) builds it step by step; the animation at the top is the
library version, [`distance_to`](libraries/spreading-and-collect.md), with real distances.

</div>

</div>

## Learning path

Start here, in order: each step builds on the previous one. The 3D walkthrough is apart,
on its own full-screen page.

<div class="grid cards" markdown>

-   :material-lightbulb-outline:{ .lg .middle } __[1. Thinking in fields](concepts/aggregate-programs.md)__

    ---

    Fields, rounds (*Sense → Compute → Act*), and the local and global reading of a program.

-   :material-school-outline:{ .lg .middle } __[2. Step-by-step tutorial](tutorial.md)__

    ---

    Build the gradient from scratch, watch it self-heal, and compose blocks into a channel.

-   :material-play-circle-outline:{ .lg .middle } __[3. Browser playground](playground/index.md)__

    ---

    Write a program and watch it run on a network in 3D, in your browser: watch any expression on every device.

-   :material-cube-outline:{ .lg .middle } __[Interactive 3D walkthrough](walkthrough/index.md)__

    ---

    Apart, full screen: a field, neighbors, a gradient, a channel and a branch, round by
    round, in 3D.

</div>

Then go deeper:

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } __[Core concepts](concepts/state.md)__

    ---

    [`remember`](concepts/state.md), [`neighbors` and `exchange`](concepts/neighborhood-field.md),
    [alignment with `@aggregate`](concepts/alignment.md), and the [common pitfalls](pitfalls.md).

-   :material-puzzle-outline:{ .lg .middle } __[Standard libraries](concepts/libraries.md)__

    ---

    [Spreading, collection and gossip](libraries/spreading-and-collect.md),
    [leader election and processes](libraries/self-organisation.md),
    [time and logic](libraries/time-and-logic.md).

-   :material-flask-outline:{ .lg .middle } __[Simulator & integration](simulator.md)__

    ---

    Experiments with animations and CSV export, [VMAS](integration/vmas.md), and
    [your own runtime](integration/index.md).

-   :material-api:{ .lg .middle } __[API reference](reference/calculus.md)__

    ---

    Every module, function and class, generated from the docstrings.

</div>

## Heritage & acknowledgments

**phyelds** builds upon over a decade of research and open-source tools in spatial and aggregate computing, bringing ideas from **[Proto](https://proto.bbn.com/)**, **[Protelis](https://protelis.github.io/)**, **[ScaFi](https://scafi.github.io/)**, **[FCPP](https://fcpp.github.io/)**, and **[Collektive](https://github.com/Collektive/collektive)** into a pragmatic, Python-native library.

- **Main contributors**: [Gianluca Aguzzi](https://github.com/cric96) and [Davide Domini](https://github.com/davidedomini).
- **Acknowledgments**: special thanks to **Mirko Viroli**, **Danilo Pianini**, **Roberto Casadei**, and **Giorgio Audrito** for the insightful discussions and foundational work that made this project possible.

# Alignment and `@aggregate`

## What alignment is

When a device calls `neighbors(x)`, it does not receive *every* value its neighbors shared during their round: it only receives the values they shared **at the exact same point of the program**.

Matching these points across devices is called **alignment**, and it is what makes aggregate functions safely composable: two independent gradients in the same program never mix their messages.

**phyelds** identifies each point in the execution by its **call path**: the stack of `@aggregate` calls leading to it, tagged with each call's sequential index among its siblings:

```python
@aggregate
def program():
    a = neighbors(1)            # path: program@0 / neighbors@0
    b = neighbors(2)            # path: program@0 / neighbors@1
    return hop_gradient(False)  # path: program@0 / hop_gradient@2 / ...
```

<div class="ph-figure">
<svg viewBox="0 0 760 190" role="img" aria-label="Call-path alignment tree">
  <defs>
    <marker id="ph-al-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--ph-diag-magenta)" />
    </marker>
  </defs>

  <!-- Root: program@0 -->
  <rect x="295" y="12" width="170" height="36" rx="6" fill="#b4136f" />
  <text x="380" y="35" text-anchor="middle" font-size="12" font-weight="700" class="ph-code" fill="#ffffff">program@0</text>

  <!-- Branches from program@0 -->
  <line x1="335" y1="48" x2="135" y2="84" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-al-arr)" />
  <line x1="380" y1="48" x2="380" y2="84" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-al-arr)" />
  <line x1="425" y1="48" x2="615" y2="84" stroke="var(--ph-diag-magenta)" stroke-width="1.8" marker-end="url(#ph-al-arr)" />

  <!-- Level 1 nodes -->
  <rect x="45" y="88" width="180" height="38" rx="6" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="135" y="111" text-anchor="middle" font-size="11.5" font-weight="700" class="ph-code" fill="var(--ph-diag-text)">neighbors@0 (1)</text>

  <rect x="290" y="88" width="180" height="38" rx="6" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="380" y="111" text-anchor="middle" font-size="11.5" font-weight="700" class="ph-code" fill="var(--ph-diag-text)">neighbors@1 (2)</text>

  <rect x="525" y="88" width="180" height="38" rx="6" fill="#c55308" />
  <text x="615" y="111" text-anchor="middle" font-size="11.5" font-weight="700" class="ph-code" fill="#ffffff">hop_gradient@2</text>

  <!-- Level 2 nodes under hop_gradient@2 -->
  <line x1="585" y1="126" x2="525" y2="146" stroke="var(--ph-diag-magenta)" stroke-width="1.6" marker-end="url(#ph-al-arr)" />
  <line x1="645" y1="126" x2="695" y2="146" stroke="var(--ph-diag-magenta)" stroke-width="1.6" marker-end="url(#ph-al-arr)" />

  <rect x="445" y="150" width="145" height="30" rx="5" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="517" y="169" text-anchor="middle" font-size="11" class="ph-code" fill="var(--ph-diag-text)">remember@0</text>

  <rect x="610" y="150" width="140" height="30" rx="5" fill="var(--ph-diag-card)" stroke="var(--ph-diag-border)" stroke-width="1.5" />
  <text x="680" y="169" text-anchor="middle" font-size="11" class="ph-code" fill="var(--ph-diag-text)">neighbors@1</text>
</svg>
</div>

The very same path also keys the local state of [`remember`](state.md) and [`exchange`](neighborhood-field.md#exchange).

---

## What `@aggregate` does: automatic network splitting

`@aggregate` marks a Python function as part of the aggregate computation. When the function runs, `@aggregate` does two things:

1. **Pushes the function onto the alignment path**, so all calls inside it are scoped under its name and call index.
2. **Rewrites `if` statements and conditional expressions** (`a if cond else b`) at the AST level so that the `True` branch and the `False` branch run under distinct alignment scopes (`align_left` vs `align_right`).

Because the two branches have different alignment paths:

- **Devices that take different branches do not see each other's messages**—the network is automatically partitioned into two isolated sub-networks (domains).
- **State inside a branch that is not taken is dropped** at the end of the round.

<div class="ph-figure">
<svg viewBox="0 0 780 190" role="img" aria-label="Automatic network splitting on an if statement">
  <!-- Condition header -->
  <rect x="255" y="10" width="270" height="34" rx="6" fill="var(--ph-diag-card)" stroke="var(--ph-diag-magenta)" stroke-width="1.8" />
  <text x="390" y="31" text-anchor="middle" font-size="12" font-weight="700" class="ph-code" fill="var(--ph-diag-text)">if sense("is_robot"):</text>

  <line x1="320" y1="44" x2="195" y2="72" stroke="var(--ph-diag-magenta)" stroke-width="1.8" />
  <line x1="460" y1="44" x2="585" y2="72" stroke="var(--ph-diag-orange)" stroke-width="1.8" />

  <!-- Left Domain: True branch -->
  <rect x="20" y="72" width="340" height="106" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-magenta)" stroke-width="1.5" />
  <text x="190" y="94" text-anchor="middle" font-size="11.5" font-weight="700" class="ph-code" fill="var(--ph-diag-magenta)">True → align_left (robots only)</text>

  <line x1="128" y1="136" x2="252" y2="136" stroke="var(--ph-diag-magenta)" stroke-width="2.5" />
  <circle cx="105" cy="136" r="22" fill="#b4136f" />
  <text x="105" y="140" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Robot 1</text>
  <circle cx="275" cy="136" r="22" fill="#b4136f" />
  <text x="275" y="140" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Robot 2</text>

  <!-- Isolation barrier in the middle -->
  <line x1="390" y1="76" x2="390" y2="174" stroke="var(--ph-diag-muted)" stroke-width="1.5" stroke-dasharray="5,4" />
  <text x="390" y="128" text-anchor="middle" font-size="10" font-weight="700" fill="var(--ph-diag-muted)">isolated</text>

  <!-- Right Domain: False branch -->
  <rect x="420" y="72" width="340" height="106" rx="8" fill="var(--ph-diag-card)" stroke="var(--ph-diag-orange)" stroke-width="1.5" />
  <text x="590" y="94" text-anchor="middle" font-size="11.5" font-weight="700" class="ph-code" fill="var(--ph-diag-orange)">False → align_right (sensors only)</text>

  <line x1="528" y1="136" x2="652" y2="136" stroke="var(--ph-diag-orange)" stroke-width="2.5" />
  <circle cx="505" cy="136" r="22" fill="#c55308" />
  <text x="505" y="140" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Sensor 3</text>
  <circle cx="675" cy="136" r="22" fill="#c55308" />
  <text x="675" y="140" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">Sensor 4</text>
</svg>
</div>

```python
@aggregate
def program():
    if sense("is_robot"):
        return neighbors("robot")      # (1)!
    else:
        return neighbors("sensor")     # (2)!
```

1. Path: `program@0 / align_left@0 / neighbors@0`. Only neighbors that also took the `True` branch appear in this `NeighborhoodField`.
2. Path: `program@0 / align_right@0 / neighbors@0`. Only neighbors that also took the `False` branch appear here.

The same automatic splitting applies to Python conditional expressions (`a if c else b`). This also keeps devices aligned for all calls *after* the conditional expression, even when only one branch communicates:

```python
@aggregate
def program():
    nearest = 0.0 if sense("source") else min(neighbors(estimate()))
    return nearest, neighbors(sense("id"))  # every device meets again here!
```

A conditional expression is rewritten only when at least one of its branches contains a function call, since a branch without calls cannot communicate or hold state.

!!! warning "When AST rewriting does not apply"
    - A helper function **without `@aggregate`** does not rewrite its `if` statements and does not push a frame onto the path. Always decorate functions that call aggregate primitives (directly or indirectly) with `@aggregate`.
    - A conditional expression containing `:=`, `yield`, or `await` cannot be lifted into a lambda and is left untouched.
    - See [Common pitfalls](../pitfalls.md) for details.

To inspect how `@aggregate` rewrites a function, call `str_transformed_code(fn)` or set the environment variable `PHYELDS_DEBUG_AST=1`:

```python
from phyelds.calculus import str_transformed_code
print(str_transformed_code(program))
```

Because AST rewriting inspects the function's source code, `@aggregate` functions must be defined in a `.py` file or a Jupyter notebook cell (if source code is unavailable, such as inside `exec`, phyelds logs a warning and runs the function un-rewritten).

---

## Explicit alignment with `align`

`align(name)` opens an aligned scope manually: values shared inside the `with align(name):` block are only exchanged with neighbors that entered an `align` block with the **same `name` at the same call position**.

```python
from phyelds.calculus import aggregate, align, neighbors

@aggregate
def per_team(team: str):
    with align(team):
        return sum(neighbors(1))   # counts only neighbors belonging to the same team
```

Because the sequential call position is still part of the path, `align` does **not** make a loop safe if different devices iterate a different number of times; for dynamic multi-instance computations, use [`@process` / `spawn`](../libraries/self-organisation.md#aggregate-processes-phyeldslibrariesprocesses) or see [Common pitfalls](../pitfalls.md#a-data-dependent-number-of-aggregate-calls).

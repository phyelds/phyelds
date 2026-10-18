"""
Generate the conceptual network illustrations in ``docs/assets/``, each in the light theme
of the docs and, with ``-dark`` in its name, in the dark one:

    poetry run python docs/examples/diagrams.py
"""
from dataclasses import dataclass
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# The text column of the docs is about 690 px wide: a figure drawn this wide, in inches, is
# shown at about its own size, so a point of text stays about a pixel and a third on the page.
COLUMN_WIDTH = 7.0
DPI = 200
TITLE = 12.0
TEXT = 10.0
SMALL = 9.0

# The fills, under white text in both themes.
MAGENTA = "#b4136f"
ORANGE = "#c55308"
PURPLE = "#6b21a8"
GOLD = "#f59e0b"
GREY_EDGE = "#94a3b8"


@dataclass(frozen=True)
class Theme:
    """The colours of a figure on the pages of one theme, and the suffix of its file."""

    suffix: str
    background: str
    card: str
    border: str
    text: str
    muted: str
    # Lines and text: on the dark pages, the lighter accents of the docs.
    magenta: str
    orange: str
    purple: str
    magenta_tint: str
    orange_tint: str
    rim: str  # around a filled shape, parting it from the lines behind
    faint: str  # devices out of range
    warning: str
    warning_tint: str


LIGHT = Theme(
    suffix="", background="#fefbf4", card="#f6efe4", border="#d6c7b2", text="#1f1a24", muted="#6b5e72",
    magenta=MAGENTA, orange=ORANGE, purple=PURPLE, magenta_tint="#fce7f3", orange_tint="#ffedd5",
    rim="#ffffff", faint="#e2e8f0", warning="#b91c1c", warning_tint="#fef2f2",
)
DARK = Theme(
    suffix="-dark", background="#1f1a24", card="#2a2430", border="#4a4352", text="#ede7f1", muted="#a59cad",
    magenta="#f472b6", orange="#ffb061", purple="#c084fc", magenta_tint="#4a2a42", orange_tint="#4a3428",
    rim="#2a2430", faint="#3a3442", warning="#f87171", warning_tint="#40222a",
)


def _canvas(theme: Theme, height: float) -> tuple[plt.Figure, plt.Axes]:
    """Open a figure as wide as the docs column, whose data units are inches."""
    fig, ax = plt.subplots(figsize=(COLUMN_WIDTH, height), dpi=DPI)
    fig.patch.set_facecolor(theme.background)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(0.0, COLUMN_WIDTH)
    ax.set_ylim(0.0, height)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _save(fig: plt.Figure, theme: Theme, name: str) -> None:
    """Write a figure to ``docs/assets/`` under the name of its theme."""
    fig.savefig(ASSETS / f"{name}{theme.suffix}.png", dpi=DPI, facecolor=theme.background)
    plt.close(fig)


def _box(
    ax: plt.Axes,
    xy: tuple[float, float],
    size: tuple[float, float],
    face: str,
    edge: str,
    lw: float = 1.4,
    linestyle: str = "-",
    rounding: float = 0.12,
    zorder: int = 2,
) -> None:
    """Draw a rounded box from its lower left corner."""
    ax.add_patch(mpatches.FancyBboxPatch(
        xy, *size,
        boxstyle=f"round,pad=0,rounding_size={rounding}",
        facecolor=face, edgecolor=edge, linewidth=lw, linestyle=linestyle, zorder=zorder,
    ))


def _draw_card(ax: plt.Axes, theme: Theme, xy: tuple[float, float], size: tuple[float, float],
               title: str = "", color: str = "") -> None:
    """Draw a rounded card frame, with a bold title at its top when given one."""
    _box(ax, xy, size, theme.card, theme.border, lw=1.5, rounding=0.2, zorder=0)
    if title:
        ax.text(xy[0] + size[0] / 2, xy[1] + size[1] - 0.3, title, ha="center", va="center",
                fontsize=TITLE, fontweight="bold", color=color, zorder=5)


def _node(ax: plt.Axes, center: tuple[float, float], radius: float, face: str, edge: str, label: str,
          color: str, size: float = TEXT, lw: float = 2.0) -> None:
    """Draw a device as a circle with its label inside."""
    ax.add_patch(Circle(center, radius, facecolor=face, edgecolor=edge, lw=lw, zorder=4))
    ax.text(*center, label, ha="center", va="center", fontsize=size, fontweight="bold", color=color, zorder=5)


def _tag(ax: plt.Axes, xy: tuple[float, float], text: str, color: str, face: str, mono: bool = True,
         size: float = SMALL) -> None:
    """Write a short bold label in a rounded frame of its colour."""
    ax.text(*xy, text, ha="center", va="center", fontsize=size, fontweight="bold", color=color,
            family="monospace" if mono else None, zorder=7,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": face, "edgecolor": color, "lw": 1.2})


def _arrow(
    ax: plt.Axes,
    p1: tuple[float, float],
    p2: tuple[float, float],
    color: str,
    rad: float = 0.0,
    shrink_a: float = 20,
    shrink_b: float = 20,
    lw: float = 2.0,
    style: str = "-|>",
    zorder: int = 3,
) -> None:
    """Draw a curved arrow between two points, automatically shrinking around node circles."""
    patch = FancyArrowPatch(
        p1,
        p2,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle=f"{style},head_length=6,head_width=4",
        color=color,
        linewidth=lw,
        shrinkA=shrink_a,
        shrinkB=shrink_b,
        zorder=zorder,
    )
    ax.add_patch(patch)


def draw_local_vs_global(theme: Theme = LIGHT) -> None:
    """Generate ``local-vs-global.png`` comparing local 1-hop interaction and global field."""
    fig, ax = _canvas(theme, 4.0)

    # Left card: what one device does.
    _draw_card(ax, theme, (0.06, 0.06), (3.38, 3.88), "1. Local view", theme.orange)
    center = (1.75, 2.0)
    ax.add_patch(Circle(center, 1.15, facecolor=theme.orange_tint, edgecolor=theme.orange,
                        linestyle="--", linewidth=1.4, alpha=0.65, zorder=1))
    ax.text(1.75, 0.3, "one device, talking to its neighbors", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    for distant in [(0.33, 2.2), (3.17, 2.2), (0.33, 1.0), (3.17, 1.0)]:
        ax.add_patch(Circle(distant, 0.15, facecolor=theme.faint, edgecolor=GREY_EDGE, lw=1.2, zorder=2))

    for label, pos in {"Nbr A": (0.85, 2.7), "Nbr B": (2.65, 2.7), "Nbr C": (1.75, 0.88)}.items():
        _arrow(ax, pos, center, theme.orange, rad=0.18, shrink_a=23, shrink_b=35, lw=1.8)
        _arrow(ax, center, pos, theme.magenta, rad=0.18, shrink_a=35, shrink_b=23, lw=1.8)
        _node(ax, pos, 0.31, theme.background, theme.orange, label, theme.text, size=SMALL)

    ax.add_patch(Circle(center, 0.46, facecolor=MAGENTA, edgecolor=theme.rim, lw=2.2, zorder=4))
    ax.text(center[0], center[1] + 0.09, "Device i", ha="center", va="center",
            fontsize=TEXT, fontweight="bold", color="#ffffff", zorder=5)
    ax.text(center[0], center[1] - 0.15, "runs round", ha="center", va="center",
            fontsize=SMALL, color="#fde047", zorder=5)

    _tag(ax, (0.6, 3.3), "inbox", theme.orange, theme.background)
    _tag(ax, (2.9, 3.3), "outbox", theme.magenta, theme.background)

    # Right card: the field the devices compute together.
    _draw_card(ax, theme, (3.56, 0.06), (3.38, 3.88), "2. Global view", theme.magenta)
    mesh_nodes = [
        (4.00, 1.19, 0.0, GOLD, "#1f1a24"),
        (4.04, 2.18, 1.0, "#ea580c", "#ffffff"),
        (4.76, 1.15, 1.1, "#ea580c", "#ffffff"),
        (4.79, 2.03, 1.3, "#e11d48", "#ffffff"),
        (4.13, 3.10, 1.9, "#db2777", "#ffffff"),
        (4.90, 3.01, 2.1, MAGENTA, "#ffffff"),
        (5.60, 1.26, 2.2, "#9d174d", "#ffffff"),
        (5.64, 2.15, 2.4, "#86198f", "#ffffff"),
        (5.73, 3.07, 2.8, PURPLE, "#ffffff"),
        (6.48, 1.31, 3.1, "#581c87", "#ffffff"),
        (6.51, 2.20, 3.3, "#4c1d95", "#ffffff"),
        (6.54, 3.05, 3.6, "#3b0764", "#ffffff"),
    ]
    edges = [
        (0, 1), (0, 2), (0, 3), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 6), (3, 5), (3, 6), (3, 7), (4, 5),
        (5, 7), (5, 8), (6, 7), (6, 9), (7, 8), (7, 9),
        (7, 10), (8, 10), (8, 11), (9, 10), (10, 11),
    ]
    for i, j in edges:
        ax.plot([mesh_nodes[i][0], mesh_nodes[j][0]], [mesh_nodes[i][1], mesh_nodes[j][1]],
                color=GREY_EDGE, lw=1.3, alpha=0.65, zorder=2)
    for nx, ny, val, fcolor, tcolor in mesh_nodes:
        _node(ax, (nx, ny), 0.28 if val == 0.0 else 0.24, fcolor, theme.rim, f"{val:.1f}", tcolor,
              size=SMALL, lw=1.6)

    ax.text(4.0, 0.7, "source", ha="center", va="center", fontsize=SMALL, fontweight="bold", color=theme.orange)
    ax.text(5.25, 0.3, "one value on every device: a field", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    _save(fig, theme, "local-vs-global")


def draw_neighbors_vs_exchange(theme: Theme = LIGHT) -> None:
    """Generate ``neighbors-vs-exchange.png`` comparing isotropic and anisotropic communication."""
    fig, ax = _canvas(theme, 3.5)

    _draw_card(ax, theme, (0.06, 0.06), (3.38, 3.38), "neighbors(v)", theme.orange)
    source = (0.75, 1.75)
    _node(ax, source, 0.42, ORANGE, theme.rim, "Device i", "#ffffff")
    for label, pos in [("Nbr A", (2.85, 2.55)), ("Nbr B", (2.85, 1.75)), ("Nbr C", (2.85, 0.95))]:
        _arrow(ax, source, pos, theme.orange, shrink_a=31, shrink_b=24)
        _tag(ax, ((source[0] + pos[0]) / 2, (source[1] + pos[1]) / 2 + 0.1), "v", theme.orange, theme.background)
        _node(ax, pos, 0.32, theme.background, theme.orange, label, theme.text, size=SMALL)
    ax.text(1.75, 0.3, "the same v to every neighbor", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    _draw_card(ax, theme, (3.56, 0.06), (3.38, 3.38), "exchange(init)", theme.magenta)
    source = (4.85, 1.75)
    _tag(ax, (3.98, 1.75), "self:\nf[i]", theme.purple, theme.magenta_tint)
    _arrow(ax, (4.43, 1.75), (4.25, 1.75), theme.purple, shrink_a=0, shrink_b=0, lw=1.8)
    _node(ax, source, 0.42, MAGENTA, theme.rim, "Device i", "#ffffff")
    for label, pos, message in [("Nbr A", (6.45, 2.55), "f[A]"), ("Nbr B", (6.45, 1.75), "f[B]"),
                                ("Nbr C", (6.45, 0.95), "f[C]")]:
        _arrow(ax, source, pos, theme.magenta, shrink_a=31, shrink_b=24)
        _tag(ax, ((source[0] + pos[0]) / 2, (source[1] + pos[1]) / 2 + 0.1), message, theme.magenta,
             theme.background)
        _node(ax, pos, 0.32, theme.background, theme.magenta, label, theme.text, size=SMALL)
    ax.text(5.25, 0.3, "its own value for each neighbor", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    _save(fig, theme, "neighbors-vs-exchange")


def draw_alignment_split(theme: Theme = LIGHT) -> None:
    """Generate ``alignment-split.png`` showing how an if statement partitions the network."""
    fig, ax = _canvas(theme, 3.3)

    _draw_card(ax, theme, (0.06, 0.06), (6.88, 3.18), 'if sense("is_robot"): the network splits', theme.magenta)

    branches = [
        (0.25, "True branch", 'neighbors("robot")', theme.magenta, theme.magenta_tint, MAGENTA,
         [("Robot 1", (0.85, 0.85)), ("Robot 2", (1.75, 1.5)), ("Robot 3", (2.65, 0.85))]),
        (3.75, "False branch", 'neighbors("sensor")', theme.orange, theme.orange_tint, ORANGE,
         [("Sensor 4", (4.35, 0.85)), ("Sensor 5", (5.25, 1.5)), ("Sensor 6", (6.15, 0.85))]),
    ]
    for x, title, call, color, tint, fill, devices in branches:
        _box(ax, (x, 0.25), (3.0, 2.45), tint, color, rounding=0.18, zorder=1)
        ax.text(x + 1.5, 2.45, title, ha="center", va="center", fontsize=TEXT, fontweight="bold", color=color)
        ax.text(x + 1.5, 2.17, call, ha="center", va="center", fontsize=SMALL, family="monospace", color=color)
        for i, (_, start) in enumerate(devices):
            for _, end in devices[i + 1:]:
                ax.plot([start[0], end[0]], [start[1], end[1]], color=color, lw=2.2, zorder=2)
        for name, pos in devices:
            _node(ax, pos, 0.37, fill, theme.rim, name, "#ffffff", size=SMALL, lw=1.8)

    ax.plot([2.65, 4.35], [0.85, 0.85], color=GREY_EDGE, lw=1.4, linestyle=":", zorder=2)
    ax.plot([3.5, 3.5], [0.35, 2.6], color=theme.muted, lw=1.6, linestyle="--", zorder=3)
    _tag(ax, (3.5, 1.5), "no messages\ncross branches", theme.text, theme.background, mono=False)

    _save(fig, theme, "alignment-split")


def draw_collect_strategies(theme: Theme = LIGHT) -> None:
    """Generate ``collect-strategies.png`` comparing single-parent tree and multi-path DAG."""
    fig, ax = _canvas(theme, 3.3)

    _draw_card(ax, theme, (0.06, 0.06), (3.38, 3.18), "point_to_point()", theme.orange)
    leaf, par_a, par_b, sink = (0.55, 1.6), (1.75, 2.4), (1.75, 0.9), (2.95, 1.65)
    ax.plot([leaf[0], par_b[0]], [leaf[1], par_b[1]], color=GREY_EDGE, lw=1.3, linestyle="--", zorder=1)
    _arrow(ax, leaf, par_a, theme.orange, shrink_a=26, shrink_b=26, lw=2.2)
    _arrow(ax, par_a, sink, theme.orange, shrink_a=26, shrink_b=26, lw=2.2)
    _arrow(ax, par_b, sink, theme.orange, shrink_a=26, shrink_b=26, lw=1.8)
    _tag(ax, (0.95, 2.2), "+10", theme.orange, theme.background)
    _tag(ax, (2.55, 2.25), "+11", theme.orange, theme.background)
    for label, pos, fill, color in [
        ("Leaf\n(10)", leaf, theme.background, theme.text),
        ("Par A\n(+1)", par_a, theme.background, theme.text),
        ("Par B\n(+1)", par_b, theme.background, theme.muted),
        ("Sink", sink, ORANGE, "#ffffff"),
    ]:
        _node(ax, pos, 0.36, fill, theme.orange, label, color, size=SMALL)
    ax.text(1.75, 0.3, "all of its total to one parent", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    _draw_card(ax, theme, (3.56, 0.06), (3.38, 3.18), "multi_path()", theme.magenta)
    leaf, par_a, par_b, sink = (4.05, 1.65), (5.25, 2.4), (5.25, 0.9), (6.45, 1.65)
    for start, end in [(leaf, par_a), (leaf, par_b), (par_a, sink), (par_b, sink)]:
        _arrow(ax, start, end, theme.magenta, shrink_a=26, shrink_b=26, lw=2.2)
    _tag(ax, (4.45, 2.25), "+5.0", theme.magenta, theme.background)
    _tag(ax, (4.45, 1.05), "+5.0", theme.magenta, theme.background)
    for label, pos, fill, color in [
        ("Leaf\n(10)", leaf, theme.background, theme.text),
        ("Par A\n(+1)", par_a, theme.background, theme.text),
        ("Par B\n(+1)", par_b, theme.background, theme.text),
        ("Sink", sink, MAGENTA, "#ffffff"),
    ]:
        _node(ax, pos, 0.36, fill, theme.magenta, label, color, size=SMALL)
    ax.text(5.25, 0.3, "split 1 / k over all parents downhill", ha="center", va="center",
            fontsize=SMALL, color=theme.muted, style="italic")

    _save(fig, theme, "collect-strategies")


def draw_slcs_regions(theme: Theme = LIGHT) -> None:
    """Generate ``slcs-regions.png`` illustrating SLCS spatial logic operators on a grid."""
    fig, ax = _canvas(theme, 3.3)

    _draw_card(ax, theme, (0.06, 0.06), (6.88, 3.18), "SLCS: the topological regions of R", theme.magenta)

    _box(ax, (0.3, 0.3), (3.3, 2.35), theme.orange_tint, theme.orange, lw=1.6, linestyle="--", rounding=0.5,
         zorder=1)
    ax.text(1.95, 2.42, "closure_boundary(R)", ha="center", va="center",
            fontsize=SMALL, fontweight="bold", family="monospace", color=theme.orange)
    _box(ax, (0.6, 0.55), (2.7, 1.68), theme.magenta_tint, theme.magenta, lw=2.2, rounding=0.4)
    ax.text(1.95, 1.98, "interior_boundary(R)", ha="center", va="center",
            fontsize=SMALL, fontweight="bold", family="monospace", color=theme.magenta)
    _box(ax, (1.0, 0.8), (1.9, 0.85), MAGENTA, theme.rim, lw=1.8, rounding=0.25, zorder=3)
    ax.text(1.95, 1.22, "interior(R)", ha="center", va="center",
            fontsize=TEXT, fontweight="bold", family="monospace", color="#ffffff", zorder=4)

    items = [
        (theme.magenta, "interior(R)", "in R, and all neighbors are in R"),
        ("#e11d48", "interior_boundary(R)", "in R, with a neighbor outside R"),
        (theme.orange, "closure_boundary(R)", "outside R, with a neighbor in R"),
        (theme.purple, "closure(R)", "R union closure_boundary(R)"),
        (theme.text, "boundary(R)", "interior_boundary union closure_boundary"),
    ]
    for row, (color, code, description) in enumerate(items):
        y = 2.5 - row * 0.48
        ax.text(3.9, y, code, ha="left", va="center", fontsize=SMALL, fontweight="bold",
                family="monospace", color=color)
        ax.text(3.9, y - 0.2, description, ha="left", va="center", fontsize=SMALL, color=theme.muted)

    _save(fig, theme, "slcs-regions")


def draw_round_lifecycle(theme: Theme = LIGHT) -> None:
    """Generate ``round-lifecycle.png`` illustrating Sense -> Compute -> Act."""
    fig, ax = _canvas(theme, 3.0)
    rows = (2.0, 1.25, 0.5)
    middle = 1.5

    def phase(x: float, title: str, color: str, entries: list[tuple[str, str, bool]]) -> None:
        _draw_card(ax, theme, (x, 0.06), (2.12, 2.88), title, color)
        for cy, (name, detail, is_code) in zip(rows, entries):
            _box(ax, (x + 0.12, cy - 0.31), (1.88, 0.62), theme.background, theme.border, lw=1.2)
            ax.text(x + 1.06, cy + 0.12, name, ha="center", va="center",
                    fontsize=TEXT, fontweight="bold", color=theme.text)
            ax.text(x + 1.06, cy - 0.13, detail, ha="center", va="center", fontsize=SMALL,
                    family="monospace" if is_code else None, color=theme.muted)

    phase(0.06, "1. Sense", theme.orange, [
        ("Device sensors", 'sense("temp")', True),
        ("Previous state", "remember / exchange", True),
        ("Neighbor inbox", "their last outboxes", False),
    ])
    for cy in rows:
        _arrow(ax, (2.06, cy), (2.6, middle + (cy - middle) * 0.4), theme.magenta, shrink_a=2, shrink_b=3, lw=1.8)

    _box(ax, (2.62, 0.45), (1.76, 2.1), MAGENTA, theme.rim, lw=2.0, rounding=0.2, zorder=3)
    ax.text(3.5, 2.22, "2. Compute", ha="center", va="center", fontsize=TITLE, fontweight="bold", color="#fde047",
            zorder=4)
    ax.text(3.5, 1.7, "@aggregate\nprogram()", ha="center", va="center", fontsize=TEXT, fontweight="bold",
            family="monospace", color="#ffffff", zorder=4)
    ax.text(3.5, 0.98, "runs top to bottom,\naligning every call\nby its path", ha="center", va="center",
            fontsize=SMALL, color="#fce7f3", zorder=4)

    for cy in rows:
        _arrow(ax, (4.4, middle + (cy - middle) * 0.4), (4.94, cy), theme.magenta, shrink_a=3, shrink_b=2, lw=1.8)
    phase(4.82, "3. Act", theme.magenta, [
        ("Actuations", 'store("motor", v)', True),
        ("Updated state", "for the next round", False),
        ("Outbox", "to current neighbors", False),
    ])

    _save(fig, theme, "round-lifecycle")


def draw_state_evolution(theme: Theme = LIGHT) -> None:
    """Generate ``state-evolution.png`` showing how remember(0) evolves across 3 rounds."""
    fig, ax = _canvas(theme, 3.9)
    rounds = [(3.365, "0", "1"), (1.965, "1", "2"), (0.565, "2", "3")]

    for number, (cy, loaded, stored) in enumerate(rounds, start=1):
        first = number == 1
        color = theme.orange if first else theme.magenta
        _draw_card(ax, theme, (0.06, cy - 0.475), (6.88, 0.95))
        ax.text(0.62, cy, f"Round {number}", ha="center", va="center", fontsize=TITLE, fontweight="bold",
                color=color)

        _box(ax, (1.2, cy - 0.33), (2.75, 0.66), theme.background, color, lw=1.5)
        ax.text(2.55, cy + 0.13, "set_count, count = remember(0)", ha="center", va="center",
                fontsize=SMALL, fontweight="bold", family="monospace", color=theme.text)
        note = "no state yet: uses the initial 0" if first else f"initial 0 ignored: loads {loaded}"
        ax.text(2.55, cy - 0.14, note, ha="center", va="center", fontsize=SMALL, fontweight="bold", color=color)
        _node(ax, (3.95, cy), 0.2, ORANGE if first else MAGENTA, theme.rim, loaded, "#ffffff", lw=1.6)

        _arrow(ax, (4.15, cy), (4.6, cy), theme.text, shrink_a=0, shrink_b=0, lw=1.6)

        _box(ax, (4.6, cy - 0.33), (2.05, 0.66), theme.magenta_tint, theme.magenta, lw=1.5)
        ax.text(5.55, cy + 0.13, f"set_count({loaded} + 1)", ha="center", va="center",
                fontsize=TEXT, fontweight="bold", family="monospace", color=theme.magenta)
        ax.text(5.55, cy - 0.14, f"stores {stored}", ha="center", va="center",
                fontsize=SMALL, fontweight="bold", color=theme.purple)
        _node(ax, (6.65, cy), 0.2, PURPLE, theme.rim, stored, "#ffffff", lw=1.6)

    # The state stored in a round is what remember loads in the next one.
    for (cy, _, stored), (next_cy, _, _) in zip(rounds, rounds[1:]):
        ax.plot([6.65, 6.65, 2.55], [cy, cy - 0.7, cy - 0.7], color=theme.purple, lw=2.3,
                solid_joinstyle="round", zorder=3)
        _arrow(ax, (2.55, cy - 0.7), (2.55, next_cy + 0.33), theme.purple, shrink_a=0, shrink_b=1, lw=2.3)
        _tag(ax, (4.6, cy - 0.7), f"state = {stored}", theme.purple, theme.background)

    _save(fig, theme, "state-evolution")


def draw_alignment_tree(theme: Theme = LIGHT) -> None:
    """Generate ``alignment-tree.png`` showing the call-path hierarchy."""
    fig, ax = _canvas(theme, 2.7)

    _draw_card(ax, theme, (0.06, 0.06), (6.88, 2.58), "Call-path alignment tree", theme.magenta)

    def node_box(cx: float, cy: float, width: float, text: str, fill: str, color: str, border: str) -> None:
        _box(ax, (cx - width / 2, cy - 0.22), (width, 0.44), fill, border, lw=1.5, zorder=4)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=TEXT, fontweight="bold",
                family="monospace", color=color, zorder=5)

    node_box(3.5, 1.85, 1.5, "program@0", MAGENTA, "#ffffff", theme.rim)
    for cx in (1.15, 3.1, 5.15):
        _arrow(ax, (3.5 + (cx - 3.5) * 0.25, 1.63), (cx, 1.32), theme.magenta, shrink_a=0, shrink_b=0, lw=1.8)
    node_box(1.15, 1.1, 1.75, "neighbors@0 (1)", theme.background, theme.text, theme.orange)
    node_box(3.1, 1.1, 1.75, "neighbors@1 (2)", theme.background, theme.text, theme.orange)
    node_box(5.15, 1.1, 1.75, "hop_gradient@2", ORANGE, "#ffffff", theme.rim)

    for cx in (4.45, 6.0):
        _arrow(ax, (5.15 + (cx - 5.15) * 0.4, 0.88), (cx, 0.62), theme.orange, shrink_a=0, shrink_b=0, lw=1.6)
    node_box(4.45, 0.4, 1.35, "remember@0", theme.background, theme.text, theme.border)
    node_box(6.0, 0.4, 1.4, "neighbors@1", theme.background, theme.text, theme.border)

    _save(fig, theme, "alignment-tree")


def draw_misaligned_loop(theme: Theme = LIGHT) -> None:
    """Generate ``misaligned-loop.png`` illustrating why data-dependent loops misalign."""
    fig, ax = _canvas(theme, 2.6)

    devices = [
        (0.06, "Device 0", 'for key in ["a", "b"]', 'neighbors@0  key = "a"', 'neighbors@1  key = "b"'),
        (4.24, "Device 1", 'for key in ["b"]', 'neighbors@0  key = "b"', "(no call at @1)"),
    ]
    for x, title, loop, first_call, second_call in devices:
        _draw_card(ax, theme, (x, 0.06), (2.7, 2.48), title, theme.text)
        ax.text(x + 1.35, 1.95, loop, ha="center", va="center", fontsize=SMALL, family="monospace",
                color=theme.muted)
        _box(ax, (x + 0.15, 1.15), (2.4, 0.5), theme.orange_tint, theme.orange, lw=1.5, zorder=3)
        ax.text(x + 1.35, 1.4, first_call, ha="center", va="center", fontsize=SMALL, fontweight="bold",
                family="monospace", color=theme.orange, zorder=4)
        missing = second_call.startswith("(")
        _box(ax, (x + 0.15, 0.35), (2.4, 0.5), theme.background, theme.border, lw=1.2,
             linestyle="--" if missing else "-", zorder=3)
        ax.text(x + 1.35, 0.6, second_call, ha="center", va="center", fontsize=SMALL, family="monospace",
                color=theme.muted, zorder=4)

    _arrow(ax, (2.55, 1.4), (4.39, 1.4), "#dc2626", style="<|-|>", shrink_a=2, shrink_b=2, lw=2.2)
    _tag(ax, (3.5, 1.95), 'Misaligned!\n"a" meets "b"', theme.warning, theme.warning_tint, mono=False)

    _save(fig, theme, "misaligned-loop")


def draw_gradient_steps(theme: Theme = LIGHT) -> None:
    """Generate ``hop-gradient-stages.png`` showing hop-gradient propagation across 3 stages."""
    fig, ax = _canvas(theme, 1.7)
    unreached = ("∞", theme.background, theme.muted)

    stages = [
        (0.06, "1. Initially", [("0", GOLD, "#1f1a24"), unreached, unreached, unreached]),
        (2.42, "2. After 1 hop", [("0", GOLD, "#1f1a24"), ("1", "#ea580c", "#ffffff"), unreached, unreached]),
        (4.78, "3. Converged", [("0", GOLD, "#1f1a24"), ("1", "#ea580c", "#ffffff"),
                                ("2", MAGENTA, "#ffffff"), ("3", PURPLE, "#ffffff")]),
    ]
    for x0, title, nodes in stages:
        _draw_card(ax, theme, (x0, 0.06), (2.16, 1.58), title, theme.magenta if title.startswith("3") else theme.orange)
        xs = [x0 + 0.33 + i * 0.5 for i in range(4)]
        ax.plot([xs[0], xs[-1]], [0.68, 0.68], color=GREY_EDGE, lw=2.0, zorder=2)
        for nx, (val, fill, color) in zip(xs, nodes):
            _node(ax, (nx, 0.68), 0.21, fill, theme.orange if val == "∞" else theme.rim, val, color, lw=1.6)

    for x in (2.22, 4.58):
        _arrow(ax, (x, 0.85), (x + 0.2, 0.85), theme.magenta, shrink_a=0, shrink_b=0, lw=2.0)

    _save(fig, theme, "hop-gradient-stages")


def main() -> None:
    """Generate all conceptual diagrams in ``docs/assets/``, in both themes."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in (LIGHT, DARK):
        draw_local_vs_global(theme)
        draw_round_lifecycle(theme)
        draw_state_evolution(theme)
        draw_neighbors_vs_exchange(theme)
        draw_alignment_tree(theme)
        draw_alignment_split(theme)
        draw_misaligned_loop(theme)
        draw_gradient_steps(theme)
        draw_collect_strategies(theme)
        draw_slcs_regions(theme)


if __name__ == "__main__":
    main()

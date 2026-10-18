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


def _setup_ax(ax: plt.Axes, xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    """Configure an axes with equal aspect, no ticks, and a rounded card background."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")


def _draw_card(ax: plt.Axes, theme: Theme, x: float, y: float, w: float, h: float, title: str, color: str) -> None:
    """Draw a rounded card frame with a bold header inside an axes."""
    box = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.08,rounding_size=0.22",
        facecolor=theme.card,
        edgecolor=theme.border,
        linewidth=1.5,
        zorder=0,
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h - 0.32,
        title,
        ha="center",
        va="center",
        fontsize=11.5,
        fontweight="bold",
        color=color,
        zorder=5,
    )


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
    fig, ax = plt.subplots(figsize=(11.2, 4.4), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 11.2), (0.0, 4.4))

    # Left Card: Local View
    _draw_card(ax, theme, 0.15, 0.15, 4.55, 4.1, "1. Local View (what one device does)", theme.orange)

    center = (2.42, 2.05)
    radius_circle = Circle(
        center,
        1.42,
        facecolor=theme.orange_tint,
        edgecolor=theme.orange,
        linestyle="--",
        linewidth=1.4,
        alpha=0.65,
        zorder=1,
    )
    ax.add_patch(radius_circle)
    ax.text(2.42, 0.42, "communication range (neighbors only)", ha="center", va="center",
            fontsize=8.8, color=theme.muted, style="italic")

    # Distant nodes outside range
    for gx, gy in [(0.62, 3.35), (0.65, 0.85), (4.22, 3.35), (4.20, 0.85)]:
        ax.add_patch(Circle((gx, gy), 0.2, facecolor=theme.faint, edgecolor=GREY_EDGE, lw=1.2, zorder=2))

    # Immediate neighbors
    neighbors_pos = {
        "Nbr A": (1.35, 2.68),
        "Nbr B": (3.50, 2.68),
        "Nbr C": (2.42, 0.92),
    }
    for label, pos in neighbors_pos.items():
        _arrow(ax, pos, center, theme.orange, rad=0.18, shrink_a=19, shrink_b=26, lw=1.8)
        _arrow(ax, center, pos, theme.magenta, rad=0.18, shrink_a=26, shrink_b=19, lw=1.8)
        ax.add_patch(Circle(pos, 0.31, facecolor=theme.background, edgecolor=theme.orange, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=theme.text, zorder=5)

    # Central Device i
    ax.add_patch(Circle(center, 0.43, facecolor=MAGENTA, edgecolor=theme.rim, lw=2.2, zorder=4))
    ax.text(center[0], center[1] + 0.08, "Device i", ha="center", va="center",
            fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)
    ax.text(center[0], center[1] - 0.13, "runs round", ha="center", va="center",
            fontsize=7.8, color="#fde047", zorder=5)

    # Inbox / Outbox mini-legend
    ax.text(1.25, 3.45, "inbox", fontsize=8.5, fontweight="bold", color=theme.orange, ha="center",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": theme.background, "edgecolor": theme.orange, "lw": 1.0})
    ax.text(3.58, 3.45, "outbox", fontsize=8.5, fontweight="bold", color=theme.magenta, ha="center",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": theme.background, "edgecolor": theme.magenta, "lw": 1.0})

    # Center Bridge
    _arrow(ax, (4.82, 2.15), (6.38, 2.15), theme.magenta, rad=0.0, shrink_a=2, shrink_b=2, lw=2.8)
    ax.text(
        5.60,
        2.62,
        "Emerges across\nspace & time",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=theme.magenta,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": theme.magenta_tint, "edgecolor": theme.magenta, "lw": 1.2},
        zorder=5,
    )

    # Right Card: Global View
    _draw_card(ax, theme, 6.50, 0.15, 4.55, 4.1, "2. Global View (the computational field)", theme.magenta)

    mesh_nodes = [
        (7.05, 1.05, 0.0, GOLD, "#1f1a24"),
        (7.10, 2.15, 1.0, "#ea580c", "#ffffff"),
        (7.92, 1.00, 1.1, "#ea580c", "#ffffff"),
        (7.95, 1.98, 1.3, "#e11d48", "#ffffff"),
        (7.20, 3.18, 1.9, "#db2777", "#ffffff"),
        (8.08, 3.08, 2.1, MAGENTA, "#ffffff"),
        (8.88, 1.12, 2.2, "#9d174d", "#ffffff"),
        (8.92, 2.12, 2.4, "#86198f", "#ffffff"),
        (9.02, 3.15, 2.8, PURPLE, "#ffffff"),
        (9.88, 1.18, 3.1, "#581c87", "#ffffff"),
        (9.92, 2.18, 3.3, "#4c1d95", "#ffffff"),
        (9.95, 3.12, 3.6, "#3b0764", "#ffffff"),
    ]
    edges = [
        (0, 1), (0, 2), (0, 3), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 6), (3, 5), (3, 6), (3, 7), (4, 5),
        (5, 7), (5, 8), (6, 7), (6, 9), (7, 8), (7, 9),
        (7, 10), (8, 10), (8, 11), (9, 10), (10, 11),
    ]
    for i, j in edges:
        ax.plot(
            [mesh_nodes[i][0], mesh_nodes[j][0]],
            [mesh_nodes[i][1], mesh_nodes[j][1]],
            color=GREY_EDGE,
            lw=1.3,
            alpha=0.65,
            zorder=2,
        )

    for nx, ny, val, fcolor, tcolor in mesh_nodes:
        radius = 0.28 if val == 0.0 else 0.24
        ax.add_patch(Circle((nx, ny), radius, facecolor=fcolor, edgecolor=theme.rim, lw=1.6, zorder=4))
        ax.text(nx, ny, f"{val:.1f}", ha="center", va="center", fontsize=8.0, fontweight="bold",
                color=tcolor, zorder=5)

    ax.text(7.05, 0.52, "Source (0.0)", ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=theme.orange)
    ax.text(9.25, 0.42, "Every device holds one value of the global field",
            ha="center", va="center", fontsize=8.8, color=theme.muted, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"local-vs-global{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_neighbors_vs_exchange(theme: Theme = LIGHT) -> None:
    """Generate ``neighbors-vs-exchange.png`` comparing isotropic and anisotropic communication."""
    fig, ax = plt.subplots(figsize=(10.5, 3.9), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 10.5), (0.0, 3.9))

    # Left Card: neighbors(v)
    _draw_card(ax, theme, 0.15, 0.15, 4.9, 3.6, "neighbors(v) — Isotropic Broadcast", theme.orange)
    src_l = (1.35, 1.85)
    ax.add_patch(Circle(src_l, 0.38, facecolor=ORANGE, edgecolor=theme.rim, lw=2.0, zorder=4))
    ax.text(src_l[0], src_l[1], "Device i", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color="#ffffff", zorder=5)

    targets_l = [("Nbr A", (3.85, 2.75), "v"), ("Nbr B", (3.85, 1.85), "v"), ("Nbr C", (3.85, 0.95), "v")]
    for label, pos, msg in targets_l:
        _arrow(ax, src_l, pos, theme.orange, shrink_a=24, shrink_b=22, lw=2.0)
        mx, my = (src_l[0] + pos[0]) / 2, (src_l[1] + pos[1]) / 2
        ax.text(mx, my + 0.15, msg, ha="center", va="center", fontsize=9.5, fontweight="bold",
                family="monospace", color=theme.orange,
                bbox={"boxstyle": "round,pad=0.18", "facecolor": theme.background,
                      "edgecolor": theme.orange, "lw": 1.0},
                zorder=6)
        ax.add_patch(Circle(pos, 0.32, facecolor=theme.background, edgecolor=theme.orange, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=theme.text, zorder=5)

    ax.text(2.60, 0.40, "Sends the exact same value v to all neighbors",
            ha="center", va="center", fontsize=8.8, color=theme.muted, style="italic")

    # Right Card: exchange(init)
    _draw_card(ax, theme, 5.45, 0.15, 4.9, 3.6, "exchange(init) — Anisotropic + State", theme.magenta)
    src_r = (6.85, 1.85)
    ax.add_patch(Circle(src_r, 0.38, facecolor=MAGENTA, edgecolor=theme.rim, lw=2.0, zorder=4))
    ax.text(src_r[0], src_r[1], "Device i", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color="#ffffff", zorder=5)

    # Self state badge
    ax.text(5.88, 1.85, "self:\nf[i]", ha="center", va="center", fontsize=8.5, fontweight="bold",
            family="monospace", color=theme.purple,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": theme.magenta_tint, "edgecolor": theme.purple, "lw": 1.2},
            zorder=5)
    _arrow(ax, (6.47, 1.85), (6.18, 1.85), theme.purple, rad=0.0, shrink_a=0, shrink_b=0, lw=1.8)

    targets_r = [
        ("Nbr A", (9.35, 2.75), "f[A]"),
        ("Nbr B", (9.35, 1.85), "f[B]"),
        ("Nbr C", (9.35, 0.95), "f[C]"),
    ]
    for label, pos, msg in targets_r:
        _arrow(ax, src_r, pos, theme.magenta, shrink_a=24, shrink_b=22, lw=2.0)
        mx, my = (src_r[0] + pos[0]) / 2, (src_r[1] + pos[1]) / 2
        ax.text(mx, my + 0.15, msg, ha="center", va="center", fontsize=9.0, fontweight="bold",
                family="monospace", color=theme.magenta,
                bbox={"boxstyle": "round,pad=0.18", "facecolor": theme.background,
                      "edgecolor": theme.magenta, "lw": 1.0},
                zorder=6)
        ax.add_patch(Circle(pos, 0.32, facecolor=theme.background, edgecolor=theme.magenta, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=theme.text, zorder=5)

    ax.text(7.90, 0.40, "Keeps f[i] as state and sends custom f[nbr] per neighbor",
            ha="center", va="center", fontsize=8.8, color=theme.muted, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"neighbors-vs-exchange{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_alignment_split(theme: Theme = LIGHT) -> None:
    """Generate ``alignment-split.png`` showing how an if statement partitions the network."""
    fig, ax = plt.subplots(figsize=(10.2, 3.8), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 10.2), (0.0, 3.8))

    _draw_card(ax, theme, 0.15, 0.15, 9.9, 3.5, 'if sense("is_robot"): automatic domain splitting', theme.magenta)

    # Left sub-network: Robots (True branch)
    left_box = mpatches.FancyBboxPatch(
        (0.45, 0.45), 4.15, 2.55,
        boxstyle="round,pad=0.06,rounding_size=0.18",
        facecolor=theme.magenta_tint, edgecolor=theme.magenta, linewidth=1.4, alpha=0.55, zorder=1,
    )
    ax.add_patch(left_box)
    ax.text(2.52, 2.75, 'True branch (align_left): neighbors("robot")',
            ha="center", va="center", fontsize=9.5, fontweight="bold", family="monospace", color=theme.magenta)

    robots = [("Robot 1", (1.20, 1.45)), ("Robot 2", (2.52, 2.05)), ("Robot 3", (3.80, 1.35))]
    for i in range(len(robots)):
        for j in range(i + 1, len(robots)):
            ax.plot([robots[i][1][0], robots[j][1][0]], [robots[i][1][1], robots[j][1][1]],
                    color=theme.magenta, lw=2.2, zorder=2)
    for name, pos in robots:
        ax.add_patch(Circle(pos, 0.34, facecolor=MAGENTA, edgecolor=theme.rim, lw=1.8, zorder=4))
        ax.text(pos[0], pos[1], name, ha="center", va="center", fontsize=8.5, fontweight="bold",
                color="#ffffff", zorder=5)

    # Right sub-network: Sensors (False branch)
    right_box = mpatches.FancyBboxPatch(
        (5.60, 0.45), 4.15, 2.55,
        boxstyle="round,pad=0.06,rounding_size=0.18",
        facecolor=theme.orange_tint, edgecolor=theme.orange, linewidth=1.4, alpha=0.65, zorder=1,
    )
    ax.add_patch(right_box)
    ax.text(7.67, 2.75, 'False branch (align_right): neighbors("sensor")',
            ha="center", va="center", fontsize=9.5, fontweight="bold", family="monospace", color=theme.orange)

    sensors = [("Sensor 4", (6.40, 1.35)), ("Sensor 5", (7.67, 2.05)), ("Sensor 6", (8.95, 1.45))]
    for i in range(len(sensors)):
        for j in range(i + 1, len(sensors)):
            ax.plot([sensors[i][1][0], sensors[j][1][0]], [sensors[i][1][1], sensors[j][1][1]],
                    color=theme.orange, lw=2.2, zorder=2)
    for name, pos in sensors:
        ax.add_patch(Circle(pos, 0.34, facecolor=ORANGE, edgecolor=theme.rim, lw=1.8, zorder=4))
        ax.text(pos[0], pos[1], name, ha="center", va="center", fontsize=8.5, fontweight="bold",
                color="#ffffff", zorder=5)

    # Cross-domain blocked links
    ax.plot([3.80, 6.40], [1.35, 1.35], color=GREY_EDGE, lw=1.4, linestyle=":", zorder=2)
    ax.plot([5.10, 5.10], [0.55, 2.90], color=theme.muted, lw=1.6, linestyle="--", zorder=3)
    ax.text(
        5.10, 1.65, "No messages\ncross branches",
        ha="center", va="center", fontsize=8.5, fontweight="bold", color=theme.text,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": theme.background, "edgecolor": theme.border, "lw": 1.2},
        zorder=6,
    )

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"alignment-split{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_collect_strategies(theme: Theme = LIGHT) -> None:
    """Generate ``collect-strategies.png`` comparing single-parent tree and multi-path DAG."""
    fig, ax = plt.subplots(figsize=(10.5, 3.8), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 10.5), (0.0, 3.8))

    # Left Card: Single-parent tree
    _draw_card(ax, theme, 0.15, 0.15, 4.9, 3.5, "point_to_point() — Single-Parent Tree", theme.orange)
    leaf_t = (1.05, 1.45)
    par_a_t = (2.55, 2.45)
    par_b_t = (2.55, 1.00)
    sink_t = (4.15, 1.80)

    # Unused link to Par B
    ax.plot([leaf_t[0], par_b_t[0]], [leaf_t[1], par_b_t[1]], color=GREY_EDGE, lw=1.3, linestyle="--", zorder=1)
    _arrow(ax, leaf_t, par_a_t, theme.orange, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, par_a_t, sink_t, theme.orange, shrink_a=22, shrink_b=24, lw=2.2)
    _arrow(ax, par_b_t, sink_t, theme.orange, shrink_a=22, shrink_b=24, lw=1.8)

    ax.text(1.68, 2.22, "+10", fontsize=9, fontweight="bold", family="monospace", color=theme.orange,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": theme.background, "edgecolor": theme.orange, "lw": 1.0})
    ax.text(3.42, 2.38, "+11", fontsize=9, fontweight="bold", family="monospace", color=theme.orange,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": theme.background, "edgecolor": theme.orange, "lw": 1.0})

    for label, pos, fill, tc in [
        ("Leaf\n(10)", leaf_t, theme.background, theme.text),
        ("Par A\n(+1)", par_a_t, theme.background, theme.text),
        ("Par B\n(+1)", par_b_t, theme.background, theme.muted),
        ("Sink", sink_t, ORANGE, "#ffffff"),
    ]:
        ax.add_patch(Circle(pos, 0.34, facecolor=fill, edgecolor=theme.orange, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.2, fontweight="bold",
                color=tc, zorder=5)

    ax.text(2.60, 0.38, "Each node sends 100% of its total to a single parent",
            ha="center", va="center", fontsize=8.6, color=theme.muted, style="italic")

    # Right Card: Multi-Path DAG
    _draw_card(ax, theme, 5.45, 0.15, 4.9, 3.5, "multi_path() — Loss-Resilient DAG", theme.magenta)
    leaf_d = (6.35, 1.75)
    par_a_d = (7.85, 2.55)
    par_b_d = (7.85, 0.95)
    sink_d = (9.45, 1.75)

    _arrow(ax, leaf_d, par_a_d, theme.magenta, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, leaf_d, par_b_d, theme.magenta, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, par_a_d, sink_d, theme.magenta, shrink_a=22, shrink_b=24, lw=2.2)
    _arrow(ax, par_b_d, sink_d, theme.magenta, shrink_a=22, shrink_b=24, lw=2.2)

    ax.text(6.98, 2.38, "+5.0", fontsize=8.8, fontweight="bold", family="monospace", color=theme.magenta,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": theme.background, "edgecolor": theme.magenta, "lw": 1.0})
    ax.text(6.98, 1.12, "+5.0", fontsize=8.8, fontweight="bold", family="monospace", color=theme.magenta,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": theme.background, "edgecolor": theme.magenta, "lw": 1.0})

    for label, pos, fill, tc in [
        ("Leaf\n(10)", leaf_d, theme.background, theme.text),
        ("Par A\n(+1)", par_a_d, theme.background, theme.text),
        ("Par B\n(+1)", par_b_d, theme.background, theme.text),
        ("Sink", sink_d, MAGENTA, "#ffffff"),
    ]:
        ax.add_patch(Circle(pos, 0.34, facecolor=fill, edgecolor=theme.magenta, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.2, fontweight="bold",
                color=tc, zorder=5)

    ax.text(7.90, 0.38, "Splits contribution equally (1 / k) across all downhill parents",
            ha="center", va="center", fontsize=8.6, color=theme.muted, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"collect-strategies{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_slcs_regions(theme: Theme = LIGHT) -> None:
    """Generate ``slcs-regions.png`` illustrating SLCS spatial logic operators on a grid."""
    fig, ax = plt.subplots(figsize=(9.6, 3.8), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 9.6), (0.0, 3.8))

    _draw_card(ax, theme, 0.15, 0.15, 9.3, 3.5, "Spatial Logic for Closure Spaces (SLCS) — Topological Regions",
               theme.magenta)

    # Concentric spatial regions on the left
    # closure_boundary (outer ring)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.55, 0.48), 5.0, 2.55,
        boxstyle="round,pad=0.05,rounding_size=0.6",
        facecolor=theme.orange_tint, edgecolor=theme.orange, linewidth=1.6, linestyle="--", zorder=1,
    ))
    ax.text(3.05, 2.82, "closure_boundary(R)  [False, has neighbor in R]",
            ha="center", va="center", fontsize=8.8, fontweight="bold", family="monospace", color=theme.orange)

    # Region R (interior_boundary)
    ax.add_patch(mpatches.FancyBboxPatch(
        (1.15, 0.82), 3.8, 1.72,
        boxstyle="round,pad=0.05,rounding_size=0.45",
        facecolor=theme.magenta_tint, edgecolor=theme.magenta, linewidth=2.2, zorder=2,
    ))
    ax.text(3.05, 2.32, "interior_boundary(R)  [True, touches outside]",
            ha="center", va="center", fontsize=8.8, fontweight="bold", family="monospace", color=theme.magenta)

    # interior(R)
    ax.add_patch(mpatches.FancyBboxPatch(
        (1.85, 1.15), 2.4, 0.92,
        boxstyle="round,pad=0.05,rounding_size=0.3",
        facecolor=MAGENTA, edgecolor=theme.rim, linewidth=1.8, zorder=3,
    ))
    ax.text(3.05, 1.61, "interior(R)\n[all neighbors in R]",
            ha="center", va="center", fontsize=9.0, fontweight="bold", family="monospace", color="#ffffff", zorder=4)

    # Legend summary on the right
    items = [
        (theme.magenta, "interior(R)", "In R, and all neighbors are in R"),
        ("#e11d48", "interior_boundary(R)", "In R, with >= 1 neighbor outside R"),
        (theme.orange, "closure_boundary(R)", "Outside R, with >= 1 neighbor in R"),
        (theme.purple, "closure(R)", "R union closure_boundary(R)"),
        (theme.text, "boundary(R)", "interior_boundary union closure_boundary"),
    ]
    y_pos = 2.75
    for color, code, desc in items:
        ax.text(5.85, y_pos, code, ha="left", va="center", fontsize=8.8, fontweight="bold",
                family="monospace", color=color)
        ax.text(5.85, y_pos - 0.21, desc, ha="left", va="center", fontsize=8.2, color=theme.muted)
        y_pos -= 0.50

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"slcs-regions{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_round_lifecycle(theme: Theme = LIGHT) -> None:
    """Generate ``round-lifecycle.png`` illustrating Sense -> Compute -> Act."""
    fig, ax = plt.subplots(figsize=(10.8, 3.6), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 10.8), (0.0, 3.6))

    # Column 1: SENSE
    _draw_card(ax, theme, 0.15, 0.15, 3.15, 3.3, "1. SENSE (Inputs)", theme.orange)
    inputs = [
        (2.42, "Device Sensors", 'sense("temp"), local_position()'),
        (1.52, "Previous Local State", "from remember / exchange"),
        (0.62, "Neighbor Inbox", "aligned neighbors' last outboxes"),
    ]
    for cy, title, sub in inputs:
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.32, cy - 0.30), 2.81, 0.62,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=theme.background, edgecolor=theme.border, linewidth=1.2, zorder=2,
        ))
        ax.text(1.72, cy + 0.10, title, ha="center", va="center", fontsize=9.0, fontweight="bold", color=theme.text)
        ax.text(1.72, cy - 0.12, sub, ha="center", va="center", fontsize=7.8, family="monospace", color=theme.muted)
        _arrow(ax, (3.18, cy), (4.02, 1.52 + (cy - 1.52) * 0.35), theme.magenta, shrink_a=2, shrink_b=4, lw=1.8)

    # Column 2: COMPUTE
    ax.add_patch(mpatches.FancyBboxPatch(
        (4.05, 0.72), 2.70, 1.95,
        boxstyle="round,pad=0.06,rounding_size=0.20",
        facecolor=MAGENTA, edgecolor=theme.rim, linewidth=2.0, zorder=3,
    ))
    ax.text(5.40, 2.28, "2. COMPUTE", ha="center", va="center", fontsize=11.0, fontweight="bold", color="#fde047")
    ax.text(5.40, 1.82, "@aggregate program()", ha="center", va="center",
            fontsize=9.8, fontweight="bold", family="monospace", color="#ffffff")
    ax.text(5.40, 1.32, "Runs top-to-bottom on the device,\naligning every call by its path",
            ha="center", va="center", fontsize=8.3, color="#fce7f3")

    # Column 3: ACT
    _draw_card(ax, theme, 7.50, 0.15, 3.15, 3.3, "3. ACT (Outputs)", theme.magenta)
    outputs = [
        (2.42, "Actuations & Metrics", 'store("motor", v), return val'),
        (1.52, "Updated Local State", "kept for this device's next round"),
        (0.62, "Outbox Packet", "broadcast to current neighbors"),
    ]
    for cy, title, sub in outputs:
        _arrow(ax, (6.78, 1.52 + (cy - 1.52) * 0.35), (7.62, cy), theme.magenta, shrink_a=4, shrink_b=2, lw=1.8)
        ax.add_patch(mpatches.FancyBboxPatch(
            (7.67, cy - 0.30), 2.81, 0.62,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=theme.background, edgecolor=theme.border, linewidth=1.2, zorder=2,
        ))
        ax.text(9.07, cy + 0.10, title, ha="center", va="center", fontsize=9.0, fontweight="bold", color=theme.text)
        ax.text(9.07, cy - 0.12, sub, ha="center", va="center", fontsize=7.8, family="monospace", color=theme.muted)

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / f"round-lifecycle{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_state_evolution(theme: Theme = LIGHT) -> None:
    """Generate ``state-evolution.png`` showing how remember(0) evolves across 3 rounds."""
    fig, ax = plt.subplots(figsize=(11.0, 3.8), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 11.0), (0.0, 3.8))

    rounds = [
        (0.18, "Round 1 (first round)", True, "0", "1"),
        (3.85, "Round 2", False, "1", "2"),
        (7.52, "Round 3", False, "2", "3"),
    ]

    for x, title, is_first, loaded_val, next_val in rounds:
        _draw_card(ax, theme, x, 0.20, 3.30, 3.40, title, theme.orange if is_first else theme.magenta)
        cx = x + 1.65

        # Step A: remember(0) box
        ax.add_patch(mpatches.FancyBboxPatch(
            (x + 0.20, 2.12), 2.90, 0.85,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            facecolor=theme.background, edgecolor=theme.orange if is_first else theme.magenta, linewidth=1.5, zorder=2,
        ))
        ax.text(cx, 2.74, "set_count, count = remember(0)", ha="center", va="center",
                fontsize=8.2, fontweight="bold", family="monospace", color=theme.text)
        if is_first:
            ax.text(cx, 2.45, "no prior state -> uses initial 0", ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=theme.orange)
        else:
            ax.text(cx, 2.45, f"initial 0 ignored -> loads {loaded_val}", ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=theme.magenta)

        # Loaded value badge
        ax.add_patch(Circle((cx, 1.98), 0.22, facecolor=ORANGE if is_first else MAGENTA,
                            edgecolor=theme.rim, lw=1.6, zorder=4))
        ax.text(cx, 1.98, loaded_val, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)

        # Arrow down to set_count
        _arrow(ax, (cx, 1.74), (cx, 1.32), theme.text, shrink_a=0, shrink_b=0, lw=1.6)

        # Step B: set_count(count + 1) box
        ax.add_patch(mpatches.FancyBboxPatch(
            (x + 0.20, 0.42), 2.90, 0.82,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            facecolor=theme.magenta_tint, edgecolor=theme.magenta, linewidth=1.5, zorder=2,
        ))
        ax.text(x + 1.40, 0.98, f"set_count({loaded_val} + 1)", ha="center", va="center",
                fontsize=8.8, fontweight="bold", family="monospace", color=theme.magenta)
        ax.text(x + 1.40, 0.66, f"stores new state = {next_val}", ha="center", va="center",
                fontsize=8.0, fontweight="bold", color=theme.purple)

        # Output state badge at right of step B
        ax.add_patch(Circle((x + 2.78, 0.82), 0.22, facecolor=PURPLE,
                            edgecolor=theme.rim, lw=1.6, zorder=4))
        ax.text(x + 2.78, 0.82, next_val, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)

    # Curved state-trace arrows feeding the stored state from Round k into Round k+1's remember(0)
    traces = [
        ((0.18 + 3.00, 0.82), (3.85 + 0.20, 2.52), "state = 1"),
        ((3.85 + 3.00, 0.82), (7.52 + 0.20, 2.52), "state = 2"),
    ]
    for p_start, p_end, label in traces:
        _arrow(ax, p_start, p_end, theme.purple, rad=-0.18, shrink_a=4, shrink_b=4, lw=2.3, zorder=6)
        mx = (p_start[0] + p_end[0]) / 2
        my = (p_start[1] + p_end[1]) / 2 + 0.12
        ax.text(
            mx, my, label, ha="center", va="center",
            fontsize=8.5, fontweight="bold", family="monospace", color=theme.purple,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": theme.background, "edgecolor": theme.purple, "lw": 1.3},
            zorder=7,
        )

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / f"state-evolution{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_alignment_tree(theme: Theme = LIGHT) -> None:
    """Generate ``alignment-tree.png`` showing the call-path hierarchy."""
    fig, ax = plt.subplots(figsize=(9.5, 3.2), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 9.5), (0.0, 3.2))

    _draw_card(ax, theme, 0.15, 0.15, 9.2, 2.9, "Call-Path Alignment Tree", theme.magenta)

    def node_box(cx: float, cy: float, w: float, text: str, fill: str, tc: str, border: str = theme.border) -> None:
        ax.add_patch(mpatches.FancyBboxPatch(
            (cx - w / 2, cy - 0.25), w, 0.50,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=fill, edgecolor=border, linewidth=1.5, zorder=4,
        ))
        ax.text(cx, cy, text, ha="center", va="center", fontsize=9.0, fontweight="bold",
                family="monospace", color=tc, zorder=5)

    node_box(4.75, 2.28, 1.9, "program@0", MAGENTA, "#ffffff", theme.rim)

    _arrow(ax, (4.10, 2.00), (1.85, 1.66), theme.magenta, shrink_a=0, shrink_b=0, lw=1.8)
    _arrow(ax, (4.75, 2.00), (4.75, 1.66), theme.magenta, shrink_a=0, shrink_b=0, lw=1.8)
    _arrow(ax, (5.40, 2.00), (7.45, 1.66), theme.magenta, shrink_a=0, shrink_b=0, lw=1.8)

    node_box(1.85, 1.35, 2.3, "neighbors@0 (1)", theme.background, theme.text, theme.orange)
    node_box(4.75, 1.35, 2.3, "neighbors@1 (2)", theme.background, theme.text, theme.orange)
    node_box(7.45, 1.35, 2.3, "hop_gradient@2", ORANGE, "#ffffff", theme.rim)

    _arrow(ax, (7.05, 1.04), (6.35, 0.82), theme.orange, shrink_a=0, shrink_b=0, lw=1.6)
    _arrow(ax, (7.85, 1.04), (8.40, 0.82), theme.orange, shrink_a=0, shrink_b=0, lw=1.6)

    node_box(6.25, 0.52, 1.75, "remember@0", theme.background, theme.text, theme.border)
    node_box(8.35, 0.52, 1.75, "neighbors@1", theme.background, theme.text, theme.border)

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / f"alignment-tree{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_misaligned_loop(theme: Theme = LIGHT) -> None:
    """Generate ``misaligned-loop.png`` illustrating why data-dependent loops misalign."""
    fig, ax = plt.subplots(figsize=(9.8, 2.7), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 9.8), (0.0, 2.7))

    # Left: Device 0
    _draw_card(ax, theme, 0.15, 0.15, 3.25, 2.4, 'Device 0: iterates ["a", "b"]', theme.text)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.35, 1.35), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=theme.orange_tint, edgecolor=theme.orange, linewidth=1.5, zorder=3,
    ))
    ax.text(1.77, 1.61, 'neighbors@0  (key = "a")', ha="center", va="center",
            fontsize=8.8, fontweight="bold", family="monospace", color=theme.orange)

    ax.add_patch(mpatches.FancyBboxPatch(
        (0.35, 0.52), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=theme.background, edgecolor=theme.border, linewidth=1.2, zorder=3,
    ))
    ax.text(1.77, 0.78, 'neighbors@1  (key = "b")', ha="center", va="center",
            fontsize=8.8, family="monospace", color=theme.muted)

    # Right: Device 1
    _draw_card(ax, theme, 6.40, 0.15, 3.25, 2.4, 'Device 1: iterates ["b"]', theme.text)
    ax.add_patch(mpatches.FancyBboxPatch(
        (6.60, 1.35), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=theme.orange_tint, edgecolor=theme.orange, linewidth=1.5, zorder=3,
    ))
    ax.text(8.02, 1.61, 'neighbors@0  (key = "b")', ha="center", va="center",
            fontsize=8.8, fontweight="bold", family="monospace", color=theme.orange)

    ax.add_patch(mpatches.FancyBboxPatch(
        (6.60, 0.52), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=theme.background, edgecolor=theme.border, linewidth=1.2, linestyle="--", zorder=3,
    ))
    ax.text(8.02, 0.78, "(no call at @1)", ha="center", va="center",
            fontsize=8.8, family="monospace", color=theme.muted)

    # Misaligned connection at @0
    _arrow(ax, (3.25, 1.61), (6.55, 1.61), "#dc2626", style="<|-|>", shrink_a=2, shrink_b=2, lw=2.2)
    ax.text(
        4.90, 2.02, 'Misaligned!\n"a" paired with "b" at @0',
        ha="center", va="center", fontsize=8.8, fontweight="bold", color=theme.warning,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": theme.warning_tint, "edgecolor": "#dc2626", "lw": 1.2},
        zorder=5,
    )

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / f"misaligned-loop{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


def draw_gradient_steps(theme: Theme = LIGHT) -> None:
    """Generate ``hop-gradient-stages.png`` showing hop-gradient propagation across 3 stages."""
    fig, ax = plt.subplots(figsize=(10.5, 2.4), dpi=200)
    fig.patch.set_facecolor(theme.background)
    _setup_ax(ax, (0.0, 10.5), (0.0, 2.4))

    stages = [
        (0.15, "1. Initially", [("0", GOLD, "#1f1a24"), ("∞", theme.background, theme.muted),
                                ("∞", theme.background, theme.muted), ("∞", theme.background, theme.muted)]),
        (3.65, "2. After 1 hop", [("0", GOLD, "#1f1a24"), ("1", "#ea580c", "#ffffff"),
                                  ("∞", theme.background, theme.muted), ("∞", theme.background, theme.muted)]),
        (7.15, "3. Converged", [("0", GOLD, "#1f1a24"), ("1", "#ea580c", "#ffffff"),
                                ("2", MAGENTA, "#ffffff"), ("3", PURPLE, "#ffffff")]),
    ]
    for x0, title, nodes in stages:
        _draw_card(ax, theme, x0, 0.18, 3.20, 2.04, title, theme.orange if "Converged" not in title else theme.magenta)
        xs = [x0 + 0.45 + i * 0.76 for i in range(4)]
        ax.plot([xs[0], xs[-1]], [1.02, 1.02], color=GREY_EDGE, lw=2.0, zorder=2)
        for nx, (val, fill, tc) in zip(xs, nodes):
            edge = theme.orange if val == "∞" else theme.rim
            ax.add_patch(Circle((nx, 1.02), 0.26, facecolor=fill, edgecolor=edge, lw=1.6, zorder=4))
            ax.text(nx, 1.02, val, ha="center", va="center", fontsize=9.5, fontweight="bold",
                    color=tc, zorder=5)

    _arrow(ax, (3.38, 1.20), (3.62, 1.20), theme.magenta, shrink_a=1, shrink_b=1, lw=2.0)
    _arrow(ax, (6.88, 1.20), (7.12, 1.20), theme.magenta, shrink_a=1, shrink_b=1, lw=2.0)

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / f"hop-gradient-stages{theme.suffix}.png", dpi=200, facecolor=theme.background)
    plt.close(fig)


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

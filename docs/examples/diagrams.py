"""
Generate the conceptual network illustrations in ``docs/assets/``:

    poetry run python docs/examples/diagrams.py
"""
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

ASSETS = Path(__file__).resolve().parent.parent / "assets"

BG_CREAM = "#fefbf4"
CARD_BG = "#f6efe4"
BORDER_COLOR = "#d6c7b2"
TEXT_DARK = "#1f1a24"
TEXT_MUTED = "#6b5e72"
MAGENTA = "#b4136f"
MAGENTA_LIGHT = "#fce7f3"
ORANGE = "#c55308"
ORANGE_LIGHT = "#ffedd5"
PURPLE = "#6b21a8"
GOLD = "#f59e0b"
GREY_NODE = "#cbd5e1"
GREY_EDGE = "#94a3b8"


def _setup_ax(ax: plt.Axes, xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    """Configure an axes with equal aspect, no ticks, and a rounded card background."""
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")


def _draw_card(ax: plt.Axes, x: float, y: float, w: float, h: float, title: str, color: str) -> None:
    """Draw a rounded card frame with a bold header inside an axes."""
    box = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.08,rounding_size=0.22",
        facecolor=CARD_BG,
        edgecolor=BORDER_COLOR,
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


def draw_local_vs_global() -> None:
    """Generate ``local-vs-global.png`` comparing local 1-hop interaction and global field."""
    fig, ax = plt.subplots(figsize=(11.2, 4.4), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 11.2), (0.0, 4.4))

    # Left Card: Local View
    _draw_card(ax, 0.15, 0.15, 4.55, 4.1, "1. Local View (what one device does)", ORANGE)

    center = (2.42, 2.05)
    radius_circle = Circle(
        center,
        1.42,
        facecolor=ORANGE_LIGHT,
        edgecolor=ORANGE,
        linestyle="--",
        linewidth=1.4,
        alpha=0.65,
        zorder=1,
    )
    ax.add_patch(radius_circle)
    ax.text(2.42, 0.42, "communication range (neighbors only)", ha="center", va="center",
            fontsize=8.8, color=TEXT_MUTED, style="italic")

    # Distant nodes outside range
    for gx, gy in [(0.62, 3.35), (0.65, 0.85), (4.22, 3.35), (4.20, 0.85)]:
        ax.add_patch(Circle((gx, gy), 0.2, facecolor="#e2e8f0", edgecolor=GREY_EDGE, lw=1.2, zorder=2))

    # Immediate neighbors
    neighbors_pos = {
        "Nbr A": (1.35, 2.68),
        "Nbr B": (3.50, 2.68),
        "Nbr C": (2.42, 0.92),
    }
    for label, pos in neighbors_pos.items():
        _arrow(ax, pos, center, ORANGE, rad=0.18, shrink_a=19, shrink_b=26, lw=1.8)
        _arrow(ax, center, pos, MAGENTA, rad=0.18, shrink_a=26, shrink_b=19, lw=1.8)
        ax.add_patch(Circle(pos, 0.31, facecolor=BG_CREAM, edgecolor=ORANGE, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=TEXT_DARK, zorder=5)

    # Central Device i
    ax.add_patch(Circle(center, 0.43, facecolor=MAGENTA, edgecolor="#ffffff", lw=2.2, zorder=4))
    ax.text(center[0], center[1] + 0.08, "Device i", ha="center", va="center",
            fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)
    ax.text(center[0], center[1] - 0.13, "runs round", ha="center", va="center",
            fontsize=7.8, color="#fde047", zorder=5)

    # Inbox / Outbox mini-legend
    ax.text(1.25, 3.45, "inbox", fontsize=8.5, fontweight="bold", color=ORANGE, ha="center",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": BG_CREAM, "edgecolor": ORANGE, "lw": 1.0})
    ax.text(3.58, 3.45, "outbox", fontsize=8.5, fontweight="bold", color=MAGENTA, ha="center",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": BG_CREAM, "edgecolor": MAGENTA, "lw": 1.0})

    # Center Bridge
    _arrow(ax, (4.82, 2.15), (6.38, 2.15), MAGENTA, rad=0.0, shrink_a=2, shrink_b=2, lw=2.8)
    ax.text(
        5.60,
        2.62,
        "Emerges across\nspace & time",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color=MAGENTA,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": MAGENTA_LIGHT, "edgecolor": MAGENTA, "lw": 1.2},
        zorder=5,
    )

    # Right Card: Global View
    _draw_card(ax, 6.50, 0.15, 4.55, 4.1, "2. Global View (the computational field)", MAGENTA)

    mesh_nodes = [
        (7.05, 1.05, 0.0, GOLD, TEXT_DARK),
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
        ax.add_patch(Circle((nx, ny), radius, facecolor=fcolor, edgecolor="#ffffff", lw=1.6, zorder=4))
        ax.text(nx, ny, f"{val:.1f}", ha="center", va="center", fontsize=8.0, fontweight="bold",
                color=tcolor, zorder=5)

    ax.text(7.05, 0.52, "Source (0.0)", ha="center", va="center", fontsize=8.5,
            fontweight="bold", color=ORANGE)
    ax.text(9.25, 0.42, "Every device holds one value of the global field",
            ha="center", va="center", fontsize=8.8, color=TEXT_MUTED, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "local-vs-global.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_neighbors_vs_exchange() -> None:
    """Generate ``neighbors-vs-exchange.png`` comparing isotropic and anisotropic communication."""
    fig, ax = plt.subplots(figsize=(10.5, 3.9), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 10.5), (0.0, 3.9))

    # Left Card: neighbors(v)
    _draw_card(ax, 0.15, 0.15, 4.9, 3.6, "neighbors(v) — Isotropic Broadcast", ORANGE)
    src_l = (1.35, 1.85)
    ax.add_patch(Circle(src_l, 0.38, facecolor=ORANGE, edgecolor="#ffffff", lw=2.0, zorder=4))
    ax.text(src_l[0], src_l[1], "Device i", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color="#ffffff", zorder=5)

    targets_l = [("Nbr A", (3.85, 2.75), "v"), ("Nbr B", (3.85, 1.85), "v"), ("Nbr C", (3.85, 0.95), "v")]
    for label, pos, msg in targets_l:
        _arrow(ax, src_l, pos, ORANGE, shrink_a=24, shrink_b=22, lw=2.0)
        mx, my = (src_l[0] + pos[0]) / 2, (src_l[1] + pos[1]) / 2
        ax.text(mx, my + 0.15, msg, ha="center", va="center", fontsize=9.5, fontweight="bold",
                family="monospace", color=ORANGE,
                bbox={"boxstyle": "round,pad=0.18", "facecolor": BG_CREAM, "edgecolor": ORANGE, "lw": 1.0},
                zorder=6)
        ax.add_patch(Circle(pos, 0.32, facecolor=BG_CREAM, edgecolor=ORANGE, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=TEXT_DARK, zorder=5)

    ax.text(2.60, 0.40, "Sends the exact same value v to all neighbors",
            ha="center", va="center", fontsize=8.8, color=TEXT_MUTED, style="italic")

    # Right Card: exchange(init)
    _draw_card(ax, 5.45, 0.15, 4.9, 3.6, "exchange(init) — Anisotropic + State", MAGENTA)
    src_r = (6.85, 1.85)
    ax.add_patch(Circle(src_r, 0.38, facecolor=MAGENTA, edgecolor="#ffffff", lw=2.0, zorder=4))
    ax.text(src_r[0], src_r[1], "Device i", ha="center", va="center",
            fontsize=9.2, fontweight="bold", color="#ffffff", zorder=5)

    # Self state badge
    ax.text(5.88, 1.85, "self:\nf[i]", ha="center", va="center", fontsize=8.5, fontweight="bold",
            family="monospace", color=PURPLE,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": MAGENTA_LIGHT, "edgecolor": PURPLE, "lw": 1.2},
            zorder=5)
    _arrow(ax, (6.47, 1.85), (6.18, 1.85), PURPLE, rad=0.0, shrink_a=0, shrink_b=0, lw=1.8)

    targets_r = [
        ("Nbr A", (9.35, 2.75), "f[A]"),
        ("Nbr B", (9.35, 1.85), "f[B]"),
        ("Nbr C", (9.35, 0.95), "f[C]"),
    ]
    for label, pos, msg in targets_r:
        _arrow(ax, src_r, pos, MAGENTA, shrink_a=24, shrink_b=22, lw=2.0)
        mx, my = (src_r[0] + pos[0]) / 2, (src_r[1] + pos[1]) / 2
        ax.text(mx, my + 0.15, msg, ha="center", va="center", fontsize=9.0, fontweight="bold",
                family="monospace", color=MAGENTA,
                bbox={"boxstyle": "round,pad=0.18", "facecolor": BG_CREAM, "edgecolor": MAGENTA, "lw": 1.0},
                zorder=6)
        ax.add_patch(Circle(pos, 0.32, facecolor=BG_CREAM, edgecolor=MAGENTA, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.8, fontweight="bold",
                color=TEXT_DARK, zorder=5)

    ax.text(7.90, 0.40, "Keeps f[i] as state and sends custom f[nbr] per neighbor",
            ha="center", va="center", fontsize=8.8, color=TEXT_MUTED, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "neighbors-vs-exchange.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_alignment_split() -> None:
    """Generate ``alignment-split.png`` showing how an if statement partitions the network."""
    fig, ax = plt.subplots(figsize=(10.2, 3.8), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 10.2), (0.0, 3.8))

    _draw_card(ax, 0.15, 0.15, 9.9, 3.5, 'if sense("is_robot"): automatic domain splitting', MAGENTA)

    # Left sub-network: Robots (True branch)
    left_box = mpatches.FancyBboxPatch(
        (0.45, 0.45), 4.15, 2.55,
        boxstyle="round,pad=0.06,rounding_size=0.18",
        facecolor=MAGENTA_LIGHT, edgecolor=MAGENTA, linewidth=1.4, alpha=0.55, zorder=1,
    )
    ax.add_patch(left_box)
    ax.text(2.52, 2.75, 'True branch (align_left): neighbors("robot")',
            ha="center", va="center", fontsize=9.5, fontweight="bold", family="monospace", color=MAGENTA)

    robots = [("Robot 1", (1.20, 1.45)), ("Robot 2", (2.52, 2.05)), ("Robot 3", (3.80, 1.35))]
    for i in range(len(robots)):
        for j in range(i + 1, len(robots)):
            ax.plot([robots[i][1][0], robots[j][1][0]], [robots[i][1][1], robots[j][1][1]],
                    color=MAGENTA, lw=2.2, zorder=2)
    for name, pos in robots:
        ax.add_patch(Circle(pos, 0.34, facecolor=MAGENTA, edgecolor="#ffffff", lw=1.8, zorder=4))
        ax.text(pos[0], pos[1], name, ha="center", va="center", fontsize=8.5, fontweight="bold",
                color="#ffffff", zorder=5)

    # Right sub-network: Sensors (False branch)
    right_box = mpatches.FancyBboxPatch(
        (5.60, 0.45), 4.15, 2.55,
        boxstyle="round,pad=0.06,rounding_size=0.18",
        facecolor=ORANGE_LIGHT, edgecolor=ORANGE, linewidth=1.4, alpha=0.65, zorder=1,
    )
    ax.add_patch(right_box)
    ax.text(7.67, 2.75, 'False branch (align_right): neighbors("sensor")',
            ha="center", va="center", fontsize=9.5, fontweight="bold", family="monospace", color=ORANGE)

    sensors = [("Sensor 4", (6.40, 1.35)), ("Sensor 5", (7.67, 2.05)), ("Sensor 6", (8.95, 1.45))]
    for i in range(len(sensors)):
        for j in range(i + 1, len(sensors)):
            ax.plot([sensors[i][1][0], sensors[j][1][0]], [sensors[i][1][1], sensors[j][1][1]],
                    color=ORANGE, lw=2.2, zorder=2)
    for name, pos in sensors:
        ax.add_patch(Circle(pos, 0.34, facecolor=ORANGE, edgecolor="#ffffff", lw=1.8, zorder=4))
        ax.text(pos[0], pos[1], name, ha="center", va="center", fontsize=8.5, fontweight="bold",
                color="#ffffff", zorder=5)

    # Cross-domain blocked links
    ax.plot([3.80, 6.40], [1.35, 1.35], color=GREY_EDGE, lw=1.4, linestyle=":", zorder=2)
    ax.plot([5.10, 5.10], [0.55, 2.90], color=TEXT_MUTED, lw=1.6, linestyle="--", zorder=3)
    ax.text(
        5.10, 1.65, "No messages\ncross branches",
        ha="center", va="center", fontsize=8.5, fontweight="bold", color=TEXT_DARK,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": BG_CREAM, "edgecolor": BORDER_COLOR, "lw": 1.2},
        zorder=6,
    )

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "alignment-split.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_collect_strategies() -> None:
    """Generate ``collect-strategies.png`` comparing single-parent tree and multi-path DAG."""
    fig, ax = plt.subplots(figsize=(10.5, 3.8), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 10.5), (0.0, 3.8))

    # Left Card: Single-parent tree
    _draw_card(ax, 0.15, 0.15, 4.9, 3.5, "point_to_point() — Single-Parent Tree", ORANGE)
    leaf_t = (1.05, 1.45)
    par_a_t = (2.55, 2.45)
    par_b_t = (2.55, 1.00)
    sink_t = (4.15, 1.80)

    # Unused link to Par B
    ax.plot([leaf_t[0], par_b_t[0]], [leaf_t[1], par_b_t[1]], color=GREY_EDGE, lw=1.3, linestyle="--", zorder=1)
    _arrow(ax, leaf_t, par_a_t, ORANGE, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, par_a_t, sink_t, ORANGE, shrink_a=22, shrink_b=24, lw=2.2)
    _arrow(ax, par_b_t, sink_t, ORANGE, shrink_a=22, shrink_b=24, lw=1.8)

    ax.text(1.68, 2.22, "+10", fontsize=9, fontweight="bold", family="monospace", color=ORANGE,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": BG_CREAM, "edgecolor": ORANGE, "lw": 1.0})
    ax.text(3.42, 2.38, "+11", fontsize=9, fontweight="bold", family="monospace", color=ORANGE,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": BG_CREAM, "edgecolor": ORANGE, "lw": 1.0})

    for label, pos, fill, tc in [
        ("Leaf\n(10)", leaf_t, BG_CREAM, TEXT_DARK),
        ("Par A\n(+1)", par_a_t, BG_CREAM, TEXT_DARK),
        ("Par B\n(+1)", par_b_t, BG_CREAM, TEXT_MUTED),
        ("Sink", sink_t, ORANGE, "#ffffff"),
    ]:
        ax.add_patch(Circle(pos, 0.34, facecolor=fill, edgecolor=ORANGE, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.2, fontweight="bold",
                color=tc, zorder=5)

    ax.text(2.60, 0.38, "Each node sends 100% of its total to a single parent",
            ha="center", va="center", fontsize=8.6, color=TEXT_MUTED, style="italic")

    # Right Card: Multi-Path DAG
    _draw_card(ax, 5.45, 0.15, 4.9, 3.5, "multi_path() — Loss-Resilient DAG", MAGENTA)
    leaf_d = (6.35, 1.75)
    par_a_d = (7.85, 2.55)
    par_b_d = (7.85, 0.95)
    sink_d = (9.45, 1.75)

    _arrow(ax, leaf_d, par_a_d, MAGENTA, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, leaf_d, par_b_d, MAGENTA, shrink_a=22, shrink_b=22, lw=2.2)
    _arrow(ax, par_a_d, sink_d, MAGENTA, shrink_a=22, shrink_b=24, lw=2.2)
    _arrow(ax, par_b_d, sink_d, MAGENTA, shrink_a=22, shrink_b=24, lw=2.2)

    ax.text(6.98, 2.38, "+5.0", fontsize=8.8, fontweight="bold", family="monospace", color=MAGENTA,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": BG_CREAM, "edgecolor": MAGENTA, "lw": 1.0})
    ax.text(6.98, 1.12, "+5.0", fontsize=8.8, fontweight="bold", family="monospace", color=MAGENTA,
            bbox={"boxstyle": "round,pad=0.15", "facecolor": BG_CREAM, "edgecolor": MAGENTA, "lw": 1.0})

    for label, pos, fill, tc in [
        ("Leaf\n(10)", leaf_d, BG_CREAM, TEXT_DARK),
        ("Par A\n(+1)", par_a_d, BG_CREAM, TEXT_DARK),
        ("Par B\n(+1)", par_b_d, BG_CREAM, TEXT_DARK),
        ("Sink", sink_d, MAGENTA, "#ffffff"),
    ]:
        ax.add_patch(Circle(pos, 0.34, facecolor=fill, edgecolor=MAGENTA, lw=2.0, zorder=4))
        ax.text(pos[0], pos[1], label, ha="center", va="center", fontsize=8.2, fontweight="bold",
                color=tc, zorder=5)

    ax.text(7.90, 0.38, "Splits contribution equally (1 / k) across all downhill parents",
            ha="center", va="center", fontsize=8.6, color=TEXT_MUTED, style="italic")

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "collect-strategies.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_slcs_regions() -> None:
    """Generate ``slcs-regions.png`` illustrating SLCS spatial logic operators on a grid."""
    fig, ax = plt.subplots(figsize=(9.6, 3.8), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 9.6), (0.0, 3.8))

    _draw_card(ax, 0.15, 0.15, 9.3, 3.5, "Spatial Logic for Closure Spaces (SLCS) — Topological Regions", MAGENTA)

    # Concentric spatial regions on the left
    # closure_boundary (outer ring)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.55, 0.48), 5.0, 2.55,
        boxstyle="round,pad=0.05,rounding_size=0.6",
        facecolor=ORANGE_LIGHT, edgecolor=ORANGE, linewidth=1.6, linestyle="--", zorder=1,
    ))
    ax.text(3.05, 2.82, "closure_boundary(R)  [False, has neighbor in R]",
            ha="center", va="center", fontsize=8.8, fontweight="bold", family="monospace", color=ORANGE)

    # Region R (interior_boundary)
    ax.add_patch(mpatches.FancyBboxPatch(
        (1.15, 0.82), 3.8, 1.72,
        boxstyle="round,pad=0.05,rounding_size=0.45",
        facecolor=MAGENTA_LIGHT, edgecolor=MAGENTA, linewidth=2.2, zorder=2,
    ))
    ax.text(3.05, 2.32, "interior_boundary(R)  [True, touches outside]",
            ha="center", va="center", fontsize=8.8, fontweight="bold", family="monospace", color=MAGENTA)

    # interior(R)
    ax.add_patch(mpatches.FancyBboxPatch(
        (1.85, 1.15), 2.4, 0.92,
        boxstyle="round,pad=0.05,rounding_size=0.3",
        facecolor=MAGENTA, edgecolor="#ffffff", linewidth=1.8, zorder=3,
    ))
    ax.text(3.05, 1.61, "interior(R)\n[all neighbors in R]",
            ha="center", va="center", fontsize=9.0, fontweight="bold", family="monospace", color="#ffffff", zorder=4)

    # Legend summary on the right
    items = [
        (MAGENTA, "interior(R)", "In R, and all neighbors are in R"),
        ("#e11d48", "interior_boundary(R)", "In R, with >= 1 neighbor outside R"),
        (ORANGE, "closure_boundary(R)", "Outside R, with >= 1 neighbor in R"),
        (PURPLE, "closure(R)", "R union closure_boundary(R)"),
        (TEXT_DARK, "boundary(R)", "interior_boundary union closure_boundary"),
    ]
    y_pos = 2.75
    for color, code, desc in items:
        ax.text(5.85, y_pos, code, ha="left", va="center", fontsize=8.8, fontweight="bold",
                family="monospace", color=color)
        ax.text(5.85, y_pos - 0.21, desc, ha="left", va="center", fontsize=8.2, color=TEXT_MUTED)
        y_pos -= 0.50

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "slcs-regions.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_round_lifecycle() -> None:
    """Generate ``round-lifecycle.png`` illustrating Sense -> Compute -> Act."""
    fig, ax = plt.subplots(figsize=(10.8, 3.6), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 10.8), (0.0, 3.6))

    # Column 1: SENSE
    _draw_card(ax, 0.15, 0.15, 3.15, 3.3, "1. SENSE (Inputs)", ORANGE)
    inputs = [
        (2.42, "Device Sensors", 'sense("temp"), local_position()'),
        (1.52, "Previous Local State", "from remember / exchange"),
        (0.62, "Neighbor Inbox", "aligned neighbors' last outboxes"),
    ]
    for cy, title, sub in inputs:
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.32, cy - 0.30), 2.81, 0.62,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=BG_CREAM, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=2,
        ))
        ax.text(1.72, cy + 0.10, title, ha="center", va="center", fontsize=9.0, fontweight="bold", color=TEXT_DARK)
        ax.text(1.72, cy - 0.12, sub, ha="center", va="center", fontsize=7.8, family="monospace", color=TEXT_MUTED)
        _arrow(ax, (3.18, cy), (4.02, 1.52 + (cy - 1.52) * 0.35), MAGENTA, shrink_a=2, shrink_b=4, lw=1.8)

    # Column 2: COMPUTE
    ax.add_patch(mpatches.FancyBboxPatch(
        (4.05, 0.72), 2.70, 1.95,
        boxstyle="round,pad=0.06,rounding_size=0.20",
        facecolor=MAGENTA, edgecolor="#ffffff", linewidth=2.0, zorder=3,
    ))
    ax.text(5.40, 2.28, "2. COMPUTE", ha="center", va="center", fontsize=11.0, fontweight="bold", color="#fde047")
    ax.text(5.40, 1.82, "@aggregate program()", ha="center", va="center",
            fontsize=9.8, fontweight="bold", family="monospace", color="#ffffff")
    ax.text(5.40, 1.32, "Runs top-to-bottom on the device,\naligning every call by its path",
            ha="center", va="center", fontsize=8.3, color="#fce7f3")

    # Column 3: ACT
    _draw_card(ax, 7.50, 0.15, 3.15, 3.3, "3. ACT (Outputs)", MAGENTA)
    outputs = [
        (2.42, "Actuations & Metrics", 'store("motor", v), return val'),
        (1.52, "Updated Local State", "kept for this device's next round"),
        (0.62, "Outbox Packet", "broadcast to current neighbors"),
    ]
    for cy, title, sub in outputs:
        _arrow(ax, (6.78, 1.52 + (cy - 1.52) * 0.35), (7.62, cy), MAGENTA, shrink_a=4, shrink_b=2, lw=1.8)
        ax.add_patch(mpatches.FancyBboxPatch(
            (7.67, cy - 0.30), 2.81, 0.62,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=BG_CREAM, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=2,
        ))
        ax.text(9.07, cy + 0.10, title, ha="center", va="center", fontsize=9.0, fontweight="bold", color=TEXT_DARK)
        ax.text(9.07, cy - 0.12, sub, ha="center", va="center", fontsize=7.8, family="monospace", color=TEXT_MUTED)

    fig.tight_layout(pad=0.2)
    fig.savefig(ASSETS / "round-lifecycle.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_state_evolution() -> None:
    """Generate ``state-evolution.png`` showing how remember(0) evolves across 3 rounds."""
    fig, ax = plt.subplots(figsize=(11.0, 3.8), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 11.0), (0.0, 3.8))

    rounds = [
        (0.18, "Round 1 (first round)", True, "0", "1"),
        (3.85, "Round 2", False, "1", "2"),
        (7.52, "Round 3", False, "2", "3"),
    ]

    for x, title, is_first, loaded_val, next_val in rounds:
        _draw_card(ax, x, 0.20, 3.30, 3.40, title, ORANGE if is_first else MAGENTA)
        cx = x + 1.65

        # Step A: remember(0) box
        ax.add_patch(mpatches.FancyBboxPatch(
            (x + 0.20, 2.12), 2.90, 0.85,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            facecolor=BG_CREAM, edgecolor=ORANGE if is_first else MAGENTA, linewidth=1.5, zorder=2,
        ))
        ax.text(cx, 2.74, "set_count, count = remember(0)", ha="center", va="center",
                fontsize=8.2, fontweight="bold", family="monospace", color=TEXT_DARK)
        if is_first:
            ax.text(cx, 2.45, "no prior state -> uses initial 0", ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=ORANGE)
        else:
            ax.text(cx, 2.45, f"initial 0 ignored -> loads {loaded_val}", ha="center", va="center",
                    fontsize=8.0, fontweight="bold", color=MAGENTA)

        # Loaded value badge
        ax.add_patch(Circle((cx, 1.98), 0.22, facecolor=ORANGE if is_first else MAGENTA,
                            edgecolor="#ffffff", lw=1.6, zorder=4))
        ax.text(cx, 1.98, loaded_val, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)

        # Arrow down to set_count
        _arrow(ax, (cx, 1.74), (cx, 1.32), TEXT_DARK, shrink_a=0, shrink_b=0, lw=1.6)

        # Step B: set_count(count + 1) box
        ax.add_patch(mpatches.FancyBboxPatch(
            (x + 0.20, 0.42), 2.90, 0.82,
            boxstyle="round,pad=0.04,rounding_size=0.14",
            facecolor=MAGENTA_LIGHT, edgecolor=MAGENTA, linewidth=1.5, zorder=2,
        ))
        ax.text(x + 1.40, 0.98, f"set_count({loaded_val} + 1)", ha="center", va="center",
                fontsize=8.8, fontweight="bold", family="monospace", color=MAGENTA)
        ax.text(x + 1.40, 0.66, f"stores new state = {next_val}", ha="center", va="center",
                fontsize=8.0, fontweight="bold", color=PURPLE)

        # Output state badge at right of step B
        ax.add_patch(Circle((x + 2.78, 0.82), 0.22, facecolor=PURPLE,
                            edgecolor="#ffffff", lw=1.6, zorder=4))
        ax.text(x + 2.78, 0.82, next_val, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color="#ffffff", zorder=5)

    # Curved state-trace arrows feeding the stored state from Round k into Round k+1's remember(0)
    traces = [
        ((0.18 + 3.00, 0.82), (3.85 + 0.20, 2.52), "state = 1"),
        ((3.85 + 3.00, 0.82), (7.52 + 0.20, 2.52), "state = 2"),
    ]
    for p_start, p_end, label in traces:
        _arrow(ax, p_start, p_end, PURPLE, rad=-0.18, shrink_a=4, shrink_b=4, lw=2.3, zorder=6)
        mx = (p_start[0] + p_end[0]) / 2
        my = (p_start[1] + p_end[1]) / 2 + 0.12
        ax.text(
            mx, my, label, ha="center", va="center",
            fontsize=8.5, fontweight="bold", family="monospace", color=PURPLE,
            bbox={"boxstyle": "round,pad=0.22", "facecolor": BG_CREAM, "edgecolor": PURPLE, "lw": 1.3},
            zorder=7,
        )

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / "state-evolution.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_alignment_tree() -> None:
    """Generate ``alignment-tree.png`` showing the call-path hierarchy."""
    fig, ax = plt.subplots(figsize=(9.5, 3.2), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 9.5), (0.0, 3.2))

    _draw_card(ax, 0.15, 0.15, 9.2, 2.9, "Call-Path Alignment Tree", MAGENTA)

    def node_box(cx: float, cy: float, w: float, text: str, fill: str, tc: str, border: str = BORDER_COLOR) -> None:
        ax.add_patch(mpatches.FancyBboxPatch(
            (cx - w / 2, cy - 0.25), w, 0.50,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=fill, edgecolor=border, linewidth=1.5, zorder=4,
        ))
        ax.text(cx, cy, text, ha="center", va="center", fontsize=9.0, fontweight="bold",
                family="monospace", color=tc, zorder=5)

    node_box(4.75, 2.28, 1.9, "program@0", MAGENTA, "#ffffff", "#ffffff")

    _arrow(ax, (4.10, 2.00), (1.85, 1.66), MAGENTA, shrink_a=0, shrink_b=0, lw=1.8)
    _arrow(ax, (4.75, 2.00), (4.75, 1.66), MAGENTA, shrink_a=0, shrink_b=0, lw=1.8)
    _arrow(ax, (5.40, 2.00), (7.45, 1.66), MAGENTA, shrink_a=0, shrink_b=0, lw=1.8)

    node_box(1.85, 1.35, 2.3, "neighbors@0 (1)", BG_CREAM, TEXT_DARK, ORANGE)
    node_box(4.75, 1.35, 2.3, "neighbors@1 (2)", BG_CREAM, TEXT_DARK, ORANGE)
    node_box(7.45, 1.35, 2.3, "hop_gradient@2", ORANGE, "#ffffff", "#ffffff")

    _arrow(ax, (7.05, 1.04), (6.35, 0.82), ORANGE, shrink_a=0, shrink_b=0, lw=1.6)
    _arrow(ax, (7.85, 1.04), (8.40, 0.82), ORANGE, shrink_a=0, shrink_b=0, lw=1.6)

    node_box(6.25, 0.52, 1.75, "remember@0", BG_CREAM, TEXT_DARK, BORDER_COLOR)
    node_box(8.35, 0.52, 1.75, "neighbors@1", BG_CREAM, TEXT_DARK, BORDER_COLOR)

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / "alignment-tree.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_misaligned_loop() -> None:
    """Generate ``misaligned-loop.png`` illustrating why data-dependent loops misalign."""
    fig, ax = plt.subplots(figsize=(9.8, 2.7), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 9.8), (0.0, 2.7))

    # Left: Device 0
    _draw_card(ax, 0.15, 0.15, 3.25, 2.4, 'Device 0: iterates ["a", "b"]', TEXT_DARK)
    ax.add_patch(mpatches.FancyBboxPatch(
        (0.35, 1.35), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=ORANGE_LIGHT, edgecolor=ORANGE, linewidth=1.5, zorder=3,
    ))
    ax.text(1.77, 1.61, 'neighbors@0  (key = "a")', ha="center", va="center",
            fontsize=8.8, fontweight="bold", family="monospace", color=ORANGE)

    ax.add_patch(mpatches.FancyBboxPatch(
        (0.35, 0.52), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=BG_CREAM, edgecolor=BORDER_COLOR, linewidth=1.2, zorder=3,
    ))
    ax.text(1.77, 0.78, 'neighbors@1  (key = "b")', ha="center", va="center",
            fontsize=8.8, family="monospace", color=TEXT_MUTED)

    # Right: Device 1
    _draw_card(ax, 6.40, 0.15, 3.25, 2.4, 'Device 1: iterates ["b"]', TEXT_DARK)
    ax.add_patch(mpatches.FancyBboxPatch(
        (6.60, 1.35), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=ORANGE_LIGHT, edgecolor=ORANGE, linewidth=1.5, zorder=3,
    ))
    ax.text(8.02, 1.61, 'neighbors@0  (key = "b")', ha="center", va="center",
            fontsize=8.8, fontweight="bold", family="monospace", color=ORANGE)

    ax.add_patch(mpatches.FancyBboxPatch(
        (6.60, 0.52), 2.85, 0.52, boxstyle="round,pad=0.04,rounding_size=0.12",
        facecolor=BG_CREAM, edgecolor=BORDER_COLOR, linewidth=1.2, linestyle="--", zorder=3,
    ))
    ax.text(8.02, 0.78, "(no call at @1)", ha="center", va="center",
            fontsize=8.8, family="monospace", color=TEXT_MUTED)

    # Misaligned connection at @0
    _arrow(ax, (3.25, 1.61), (6.55, 1.61), "#dc2626", style="<|-|>", shrink_a=2, shrink_b=2, lw=2.2)
    ax.text(
        4.90, 2.02, 'Misaligned!\n"a" paired with "b" at @0',
        ha="center", va="center", fontsize=8.8, fontweight="bold", color="#b91c1c",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#fef2f2", "edgecolor": "#dc2626", "lw": 1.2},
        zorder=5,
    )

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / "misaligned-loop.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def draw_gradient_steps() -> None:
    """Generate ``hop-gradient-stages.png`` showing hop-gradient propagation across 3 stages."""
    fig, ax = plt.subplots(figsize=(10.5, 2.4), dpi=200)
    fig.patch.set_facecolor(BG_CREAM)
    _setup_ax(ax, (0.0, 10.5), (0.0, 2.4))

    stages = [
        (0.15, "1. Initially", [("0", GOLD, TEXT_DARK), ("∞", BG_CREAM, TEXT_MUTED),
                                ("∞", BG_CREAM, TEXT_MUTED), ("∞", BG_CREAM, TEXT_MUTED)]),
        (3.65, "2. After 1 hop", [("0", GOLD, TEXT_DARK), ("1", "#ea580c", "#ffffff"),
                                  ("∞", BG_CREAM, TEXT_MUTED), ("∞", BG_CREAM, TEXT_MUTED)]),
        (7.15, "3. Converged", [("0", GOLD, TEXT_DARK), ("1", "#ea580c", "#ffffff"),
                                ("2", MAGENTA, "#ffffff"), ("3", PURPLE, "#ffffff")]),
    ]
    for x0, title, nodes in stages:
        _draw_card(ax, x0, 0.18, 3.20, 2.04, title, ORANGE if "Converged" not in title else MAGENTA)
        xs = [x0 + 0.45 + i * 0.76 for i in range(4)]
        ax.plot([xs[0], xs[-1]], [1.02, 1.02], color=GREY_EDGE, lw=2.0, zorder=2)
        for nx, (val, fill, tc) in zip(xs, nodes):
            edge = ORANGE if val == "∞" else "#ffffff"
            ax.add_patch(Circle((nx, 1.02), 0.26, facecolor=fill, edgecolor=edge, lw=1.6, zorder=4))
            ax.text(nx, 1.02, val, ha="center", va="center", fontsize=9.5, fontweight="bold",
                    color=tc, zorder=5)

    _arrow(ax, (3.38, 1.20), (3.62, 1.20), MAGENTA, shrink_a=1, shrink_b=1, lw=2.0)
    _arrow(ax, (6.88, 1.20), (7.12, 1.20), MAGENTA, shrink_a=1, shrink_b=1, lw=2.0)

    fig.tight_layout(pad=0.15)
    fig.savefig(ASSETS / "hop-gradient-stages.png", dpi=200, facecolor=BG_CREAM)
    plt.close(fig)


def main() -> None:
    """Generate all conceptual diagrams in ``docs/assets/``."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    draw_local_vs_global()
    draw_round_lifecycle()
    draw_state_evolution()
    draw_neighbors_vs_exchange()
    draw_alignment_tree()
    draw_alignment_split()
    draw_misaligned_loop()
    draw_gradient_steps()
    draw_collect_strategies()
    draw_slcs_regions()


if __name__ == "__main__":
    main()

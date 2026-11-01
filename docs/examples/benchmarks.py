"""
The charts of the benchmarks page, drawn from the baseline that ``benchmarks/run.py``
measured, each in the light theme of the docs and, with ``-dark`` in its name, in the dark one:

    poetry run python docs/examples/benchmarks.py
"""
import importlib.util
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

EXAMPLES = Path(__file__).resolve().parent
ASSETS = EXAMPLES.parent / "assets"
BASELINE = EXAMPLES.parents[1] / "benchmarks" / "baseline.jsonl"


def _diagrams():
    """The conceptual figures of the docs, whose column width and themes the charts share."""
    spec = importlib.util.spec_from_file_location("diagrams_example", EXAMPLES / "diagrams.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DIAGRAMS = _diagrams()
COLUMN_WIDTH, DPI, TEXT, SMALL = _DIAGRAMS.COLUMN_WIDTH, _DIAGRAMS.DPI, _DIAGRAMS.TEXT, _DIAGRAMS.SMALL
THEMES = (_DIAGRAMS.LIGHT, _DIAGRAMS.DARK)

NAMES = {"simulator": "Simulator", "mesa": "Mesa", "vmas": "VMAS", "argos": "ARGoS", "webots": "Webots"}
AGENTS = (100, 1_000, 10_000)
# The hosts measured up to 10,000 agents, by theme: any two stay apart for every colour vision.
HOST_COLORS = {
    "": {"simulator": "#2a78d6", "mesa": "#eb6834", "argos": "#1baf7a"},
    "-dark": {"simulator": "#3987e5", "mesa": "#d95926", "argos": "#199e70"},
}
# Each stage adds a layer to the one before: one hue, darker (lighter on the dark pages) with each.
STAGES = {
    "none": "Host alone",
    "empty": "+ adapter, empty program",
    "gradient": "+ phyelds, distance_to",
}
STAGE_COLORS = {"": ("#e87ba4", "#b4136f", "#6e0b44"), "-dark": ("#b4136f", "#e0559a", "#fbb6d9")}


def baseline() -> dict[tuple[str, int, str, str], float]:
    """Agent-rounds per second of each measurement, by host, agents, layout and stage."""
    rows = [json.loads(line) for line in BASELINE.read_text(encoding="utf-8").splitlines() if line]
    return {
        (row["host"], row["nodes"], row["layout"], row["stage"]): row["agent_rounds_per_s"]
        for row in rows if "error" not in row
    }


def _compact(value: float, _position: int | None = None) -> str:
    """``value`` as an axis shows it: 100, 1K, 10M."""
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= size:
            return f"{value / size:g}{suffix}"
    return f"{value:g}"


def _axes(theme, height: float) -> tuple[plt.Figure, plt.Axes]:
    """A figure as wide as the docs column, with a recessive grid and a baseline."""
    fig, ax = plt.subplots(figsize=(COLUMN_WIDTH, height), dpi=DPI)
    fig.patch.set_facecolor(theme.background)
    ax.set_facecolor(theme.background)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme.border)
    ax.tick_params(colors=theme.muted, labelsize=SMALL, length=0, pad=6)
    ax.grid(color=theme.border, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    return fig, ax


def _log_axis(axis, ticks: list[float]) -> None:
    """A log axis that shows ``ticks`` only, as compact numbers."""
    axis.set_major_locator(FixedLocator(ticks))
    axis.set_major_formatter(FuncFormatter(_compact))
    axis.set_minor_locator(NullLocator())


def _legend(fig: plt.Figure, theme, columns: int) -> None:
    """The legend, in a row above the plot, from the left edge of the figure."""
    fig.legend(loc="upper left", bbox_to_anchor=(0.01, 0.99), ncol=columns, frameon=False,
               fontsize=SMALL, labelcolor=theme.text, handletextpad=0.5, columnspacing=1.6, borderaxespad=0.0)


def _spread(values: list[float], gap: float) -> list[float]:
    """Heights for the labels of ``values``, in their order, at least ``gap`` apart and centred on them."""
    order = sorted(range(len(values)), key=values.__getitem__)
    heights = [0.0] * len(values)
    previous = float("-inf")
    for index in order:
        heights[index] = previous = max(values[index], previous + gap)
    shift = (sum(heights) - sum(values)) / len(values)
    return [height - shift for height in heights]


def _save(fig: plt.Figure, theme, name: str) -> None:
    """Write a figure to ``docs/assets/`` under the name of its theme."""
    fig.savefig(ASSETS / f"{name}{theme.suffix}.png", dpi=DPI, facecolor=theme.background)
    plt.close(fig)


def draw_scaling(theme, data: dict) -> None:
    """Agent-rounds per second of ``distance_to`` as the agents grow, at constant density."""
    fig, ax = _axes(theme, 3.4)
    fig.subplots_adjust(left=0.11, right=0.86, bottom=0.15, top=0.88)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ends = {}
    for host, color in HOST_COLORS[theme.suffix].items():
        values = [data[host, agents, "density", "gradient"] for agents in AGENTS]
        ax.plot(AGENTS, values, color=color, linewidth=2, solid_capstyle="round", solid_joinstyle="round",
                marker="o", markersize=7, markeredgecolor=theme.background, markeredgewidth=2, label=NAMES[host])
        ends[host] = values[-1]
    ax.set_xlim(75, 13_500)
    ax.set_ylim(100, 100_000)
    _log_axis(ax.xaxis, list(AGENTS))
    _log_axis(ax.yaxis, [100, 1e3, 1e4, 1e5])
    ax.set_xlabel("Agents, at constant density", color=theme.muted, fontsize=SMALL)
    ax.set_ylabel("Agent-rounds per second", color=theme.muted, fontsize=SMALL)
    _legend(fig, theme, columns=len(ends))
    # The labels of the ends, apart: in decades, as the axis is logarithmic.
    exponents = [math.log10(value) for value in ends.values()]
    for (host, value), exponent in zip(ends.items(), _spread(exponents, gap=0.17)):
        ax.annotate(NAMES[host], (AGENTS[-1], value), xytext=(AGENTS[-1] * 1.45, 10 ** exponent),
                    va="center", fontsize=SMALL, color=theme.text, annotation_clip=False,
                    arrowprops={"arrowstyle": "-", "color": theme.muted, "linewidth": 0.6,
                                "shrinkA": 0, "shrinkB": 6})
    _save(fig, theme, "benchmarks-scaling")


def draw_layers(theme, data: dict) -> None:
    """For each host and size, the agent-rounds per second of each stage: what each layer costs."""
    rows = [(host, agents) for host in NAMES for agents in AGENTS if (host, agents, "density", "gradient") in data]
    fig, ax = _axes(theme, 0.28 * len(rows) + 1.2)
    fig.subplots_adjust(left=0.2, right=0.97, bottom=0.12, top=0.9)
    ax.set_xscale("log")
    heights, height, previous = [], 0.0, None
    for host, _ in rows:
        height -= 1.0 if previous in (None, host) else 1.6  # a gap between the hosts
        heights.append(height)
        previous = host
    colors = STAGE_COLORS[theme.suffix]
    for (host, agents), row_height in zip(rows, heights):
        values = [data.get((host, agents, "density", stage)) for stage in STAGES]
        measured = [value for value in values if value is not None]
        ax.plot([min(measured), max(measured)], [row_height] * 2, color=theme.border, linewidth=1.5, zorder=2)
        for value, color, label in zip(values, colors, STAGES.values()):
            if value is not None:
                ax.plot(value, row_height, "o", markersize=8, color=color, markeredgecolor=theme.background,
                        markeredgewidth=1.5, zorder=3, label=label if row_height == heights[0] else None)
        spread = max(measured) / min(measured) - 1
        if len(measured) > 1 and spread < 0.25:  # dots on top of each other: say so
            ax.annotate(f"stages within {spread:.0%} of each other", (max(measured), row_height),
                        xytext=(12, 0), textcoords="offset points", va="center", fontsize=SMALL, color=theme.muted)
    ax.set_yticks(heights, [f"{NAMES[host]}, {agents:,}" for host, agents in rows])
    ax.tick_params(axis="y", colors=theme.text)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(heights[-1] - 0.8, 0.2)
    ax.set_xlim(100, 2e9)
    _log_axis(ax.xaxis, [10.0 ** exponent for exponent in range(2, 10)])
    ax.set_xlabel("Agent-rounds per second, at constant density", color=theme.muted, fontsize=SMALL)
    _legend(fig, theme, columns=len(STAGES))
    _save(fig, theme, "benchmarks-layers")


def main() -> None:
    """Draw the charts of the benchmarks page in ``docs/assets/``, in both themes."""
    data = baseline()
    for theme in THEMES:
        draw_scaling(theme, data)
        draw_layers(theme, data)


if __name__ == "__main__":
    main()

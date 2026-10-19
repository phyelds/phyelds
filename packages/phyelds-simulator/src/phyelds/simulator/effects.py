"""
This module contains the effects that can be applied to the simulation rendering.
"""

import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import Literal, Optional, Any, Annotated, Tuple, List
from matplotlib import colormaps
from matplotlib.colors import Normalize, to_rgba
from pydantic import BaseModel, Field, BeforeValidator, SerializeAsAny
from phyelds.simulator import Environment


class Link:
    """
    A class to represent a link between two nodes.
    The link is represented as a tuple of two nodes.
    Note!
    Link(node1, node2) == Link(node2, node1)
    """

    def __init__(self, node1: Tuple[float, ...], node2: Tuple[float, ...]):
        self.node1 = node1
        self.node2 = node2

    def __hash__(self):
        return hash(frozenset((self.node1, self.node2)))

    def __eq__(self, other):
        if isinstance(other, Link):
            return frozenset((self.node1, self.node2)) == frozenset(
                (other.node1, other.node2)
            )
        return False


class Effect(BaseModel, ABC):
    """
    Abstract base class for effects.
    """
    z_order: int = 0

    @abstractmethod
    def apply(self, ax, environment: Environment):
        """
        Apply the effect to the matplotlib axis.
        """


class DrawEdges(Effect):
    """
    Draw edges between nodes.
    """
    type: Literal["DrawEdges"] = "DrawEdges"
    alpha: float = 0.6
    z_order: int = 0

    def apply(self, ax, environment: Environment):
        """
        Draw edges between nodes.
        """
        all_neighbors_tuple = set()
        for node in environment.nodes.values():
            neighbors = node.get_neighbors()
            for neighbor in neighbors:
                all_neighbors_tuple.add(Link(node.position, neighbor.position))
        for link in all_neighbors_tuple:
            ax.plot(
                [link.node1[0], link.node2[0]],
                [link.node1[1], link.node2[1]],
                alpha=self.alpha,
                color="gray",
                zorder=self.z_order,
            )


def _is_finite_number(value: Any) -> bool:
    """True for real numbers that are not infinite or NaN (booleans excluded)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


class DrawNodes(Effect):
    """
    Draw nodes.

    With ``color_from`` alone, ``node.data[color_from]`` is used as a matplotlib color.
    With ``cmap`` too, it is read as a number and mapped onto that colormap between
    ``vmin`` and ``vmax`` (by default, the finite values on screen); nodes whose value is
    missing, infinite or not a number are drawn in ``missing_color``.
    """
    type: Literal["DrawNodes"] = "DrawNodes"
    color_from: Optional[str] = None
    cmap: Optional[str] = None
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    missing_color: str = "lightgray"
    z_order: int = 10

    def apply(self, ax, environment: Environment):
        """
        Draw nodes.
        """
        positions = [node.position for node in environment.nodes.values()]
        if not positions:
            return
        x, y = zip(*positions)

        if self.color_from and self.cmap:
            values = [node.data.get(self.color_from) for node in environment.nodes.values()]
            ax.scatter(x, y, c=self._map_to_colors(values), zorder=self.z_order)
        elif self.color_from:
            colors = [
                node.data.get(self.color_from, "blue")
                for node in environment.nodes.values()
            ]
            ax.scatter(x, y, c=colors, zorder=self.z_order)
        else:
            ax.scatter(x, y, c="blue", zorder=self.z_order)

    def _map_to_colors(self, values: List[Any]) -> List[Tuple[float, float, float, float]]:
        finite = [value for value in values if _is_finite_number(value)]
        vmin = self.vmin if self.vmin is not None else min(finite, default=0.0)
        vmax = self.vmax if self.vmax is not None else max(finite, default=1.0)
        normalize = Normalize(vmin=vmin, vmax=vmax, clip=True)
        colormap = colormaps[self.cmap]
        missing = to_rgba(self.missing_color)
        return [
            colormap(normalize(value)) if _is_finite_number(value) else missing
            for value in values
        ]


class DrawIDs(Effect):
    """
    Draw node IDs.
    """
    type: Literal["DrawIDs"] = "DrawIDs"
    z_order: int = 20

    def apply(self, ax, environment: Environment):
        """
        Draw node IDs.
        """
        # Add node IDs as text labels
        for node in environment.nodes.values():
            ax.text(
                node.position[0] + 0.02,
                node.position[1],
                str(node.id),
                fontsize=8,
                ha="center",
                va="center",
                bbox={"facecolor": "white", "alpha": 0.1, "edgecolor": "none"},
                zorder=self.z_order,
            )


class DrawValues(Effect):
    """
    Draw the value ``node.data[value_from]`` next to each node.
    Floats are rounded to ``precision`` decimals, infinity is shown as ``∞``
    and nodes without a value are skipped. ``offset`` is the vertical distance
    between a node and its label, in data units.
    """
    type: Literal["DrawValues"] = "DrawValues"
    value_from: str = "result"
    precision: int = 1
    offset: float = 0.15
    fontsize: int = 8
    z_order: int = 20

    def apply(self, ax, environment: Environment):
        """
        Draw node values.
        """
        for node in environment.nodes.values():
            value = node.data.get(self.value_from)
            if value is None:
                continue
            ax.text(
                node.position[0],
                node.position[1] + self.offset,
                self._format(value),
                fontsize=self.fontsize,
                ha="center",
                va="bottom",
                zorder=self.z_order,
            )

    def _format(self, value: Any) -> str:
        if isinstance(value, float) and math.isinf(value):
            return "∞" if value > 0 else "-∞"
        if isinstance(value, float):
            return f"{value:.{self.precision}f}"
        return str(value)


def validate_effect(v: Any) -> Any:
    """
    Validate the effect type.
    """
    if isinstance(v, dict):
        effect_type = v.get("type")
        for sub in Effect.__subclasses__():
            # pylint: disable=unsupported-membership-test, unsubscriptable-object
            if (
                "type" in sub.model_fields
                and sub.model_fields["type"].default == effect_type
            ):
                return sub.model_validate(v)
        raise ValueError(f"Unknown effect type: {effect_type}")
    return v


EffectType = Annotated[Effect, BeforeValidator(validate_effect)]


class RenderMode(str, Enum):
    """
    Enum for render modes.
    """
    SHOW = "show"
    SAVE = "save"
    SAVE_ALL = "save_all"


class RenderConfig(BaseModel):
    """
    Configuration for the RenderMonitor.
    """

    effects: List[SerializeAsAny[EffectType]] = Field(default_factory=list)
    dt: float = 1.0
    skip: float = 0.0
    pause_duration: float = 0.001
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    mode: RenderMode = RenderMode.SHOW
    save_as: str = "simulation.mp4"
    snapshot_prefix: str = "snapshot"
    show_axis: bool = True
    title: Optional[str] = None

    def save(self, path: str):
        """
        Save the configuration to a file.
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls, path: str):
        """
        Load the configuration from a file.
        """
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
